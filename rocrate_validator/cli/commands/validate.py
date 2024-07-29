from __future__ import annotations

import os
import sys
import termios
import tty
from pathlib import Path
from typing import Optional

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.padding import Padding
from rich.pager import Pager
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

import rocrate_validator.log as logging
from rocrate_validator import services
from rocrate_validator.cli.commands.errors import handle_error
from rocrate_validator.cli.main import cli, click
from rocrate_validator.cli.utils import get_app_header_rule
from rocrate_validator.colors import get_severity_color
from rocrate_validator.events import Event, EventType, Subscriber
from rocrate_validator.models import (LevelCollection, Severity,
                                      ValidationResult)
from rocrate_validator.utils import URI, get_profiles_path, get_version

# from rich.markdown import Markdown
# from rich.table import Table

# set the default profiles path
DEFAULT_PROFILES_PATH = get_profiles_path()

# set up logging
logger = logging.getLogger(__name__)


def validate_uri(ctx, param, value):
    """
    Validate if the value is a path or a URI
    """
    if value:
        try:
            # parse the value to extract the scheme
            uri = URI(value)
            if not uri.is_remote_resource() and not uri.is_local_directory() and not uri.is_local_file():
                raise click.BadParameter(f"Invalid RO-Crate URI \"{value}\": "
                                         "it MUST be a local directory or a ZIP file (local or remote).", param=param)
            if not uri.is_available():
                raise click.BadParameter("RO-crate URI not available", param=param)
        except ValueError as e:
            logger.debug(e)
            raise click.BadParameter("Invalid RO-crate path or URI", param=param)

    return value


def get_single_char(console: Optional[Console] = None, end: str = "\n",
                    message: Optional[str] = None,
                    choices: Optional[list[str]] = None) -> str:
    """
    Get a single character from the console
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    char = None
    while char is None or (choices and char not in choices):
        if console and message:
            console.print(f"\n{message}", end="")
        try:
            tty.setraw(sys.stdin.fileno())
            char = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            if console:
                console.print(char, end=end if choices and char in choices else "")
        if choices and char not in choices:
            if console:
                console.print(f" [bold red]INVALID CHOICE[/bold red]", end=end)
    return char


@cli.command("validate")
@click.argument("rocrate-uri", callback=validate_uri, default=".")
@click.option(
    '-nff',
    '--no-fail-fast',
    is_flag=True,
    help="Disable fail fast validation mode",
    default=False,
    show_default=True
)
@click.option(
    "--profiles-path",
    type=click.Path(exists=True),
    default=DEFAULT_PROFILES_PATH,
    show_default=True,
    help="Path containing the profiles files",
)
@click.option(
    "-p",
    "--profile-identifier",
    type=click.STRING,
    default=None,
    show_default=True,
    help="Identifier of the profile to use for validation",
)
@click.option(
    '-nh',
    '--disable-profile-inheritance',
    is_flag=True,
    help="Disable inheritance of profiles",
    default=False,
    show_default=True
)
@click.option(
    "-l",
    "--requirement-severity",
    type=click.Choice([s.name for s in Severity], case_sensitive=False),
    default=Severity.REQUIRED.name,
    show_default=True,
    help="Severity of the requirements to validate",
)
@click.option(
    '-lo',
    '--requirement-severity-only',
    is_flag=True,
    help="Validate only the requirements of the specified severity (no requirements with lower severity)",
    default=False,
    show_default=True
)
@click.option(
    '--details',
    is_flag=True,
    help="Output the validation details without prompting",
    default=False,
    show_default=True
)
@click.option(
    '--no-paging',
    is_flag=True,
    help="Disable pagination of the validation details",
    default=False,
    show_default=True
)
@click.option(
    '-f',
    '--format',
    type=click.Choice(["json", "text"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format of the validation report"
)
@click.option(
    '-o',
    '--output-file',
    type=click.Path(),
    default=None,
    show_default=True,
    help="Path to the output file for the validation report",
)
@click.pass_context
def validate(ctx,
             profiles_path: Path = DEFAULT_PROFILES_PATH,
             profile_identifier: Optional[str] = None,
             disable_profile_inheritance: bool = False,
             requirement_severity: str = Severity.REQUIRED.name,
             requirement_severity_only: bool = False,
             rocrate_uri: Path = ".",
             no_fail_fast: bool = False,
             ontologies_path: Optional[Path] = None,
             no_paging: bool = False,
             details: bool = False,
             format: str = "text",
             output_file: Optional[Path] = None):
    """
    [magenta]rocrate-validator:[/magenta] Validate a RO-Crate against a profile
    """
    console: Console = ctx.obj['console']
    pager = ctx.obj['pager']
    # Get the no_paging flag
    enable_pager = not no_paging
    # Log the input parameters for debugging
    logger.debug("profiles_path: %s", os.path.abspath(profiles_path))
    logger.debug("profile_identifier: %s", profile_identifier)
    logger.debug("requirement_severity: %s", requirement_severity)
    logger.debug("requirement_severity_only: %s", requirement_severity_only)

    logger.debug("disable_inheritance: %s", disable_profile_inheritance)
    logger.debug("rocrate_uri: %s", rocrate_uri)
    logger.debug("no_fail_fast: %s", no_fail_fast)
    logger.debug("fail fast: %s", not no_fail_fast)

    if ontologies_path:
        logger.debug("ontologies_path: %s", os.path.abspath(ontologies_path))
    if rocrate_uri:
        logger.debug("rocrate_path: %s", os.path.abspath(rocrate_uri))

    try:
        # Validation settings
        validation_settings = {
            "profiles_path": profiles_path,
            "profile_identifier": profile_identifier,
            "requirement_severity": requirement_severity,
            "requirement_severity_only": requirement_severity_only,
            "inherit_profiles": not disable_profile_inheritance,
            "show_details": False,
            "details": details,
            "data_path": rocrate_uri,
            "ontology_path": Path(ontologies_path).absolute() if ontologies_path else None,
            "abort_on_first": not no_fail_fast
        }

        # Print the application header
        console.print(get_app_header_rule())

        # Detect the profile to use for validation
        autodetection = False
        selected_profile = profile_identifier
        if selected_profile is None:
            candidate_profiles = services.detect_profiles(settings=validation_settings)
            if candidate_profiles and len(candidate_profiles) == 1:
                logger.debug("Profile identifier autodetected: %s", candidate_profiles[0].identifier)
                autodetection = True
                selected_profile = candidate_profiles[0].identifier
            else:
                logger.debug("Candidate profiles: %s", candidate_profiles)
                available_profiles = services.get_profiles(profiles_path)
                # Define the list of choices
                # console.print(get_app_header_rule())
                choices = [
                    f"[bold]{profile.identifier}[/bold]: [white]{profile.name}[/white]" for profile in available_profiles]
                console.print(Padding(Rule("[bold yellow]WARNING: [/bold yellow]"
                                           "[bold]Unable to automatically detect the profile to use for validation[/bold]\n", align="center", style="bold yellow"), (2, 2, 0, 2)))
                selected_option = multiple_choice(
                    console, choices, "[italic]Available Profiles[/italic]", padding=(1, 2))
                selected_profile = available_profiles[int(selected_option) - 1].identifier
                logger.debug("Profile selected: %s", selected_profile)
                console.print(Padding(Rule(style="bold yellow"), (1, 2)))
        # Set the selected profile
        validation_settings["profile_identifier"] = selected_profile
        validation_settings["profile_autodetected"] = autodetection
        logger.debug("Profile selected for validation: %s", validation_settings["profile_identifier"])
        logger.debug("Profile autodetected: %s", autodetection)

        # Compute the profile statistics
        profile_stats = __compute_profile_stats__(validation_settings)

        report_layout = ValidationReportLayout(console, validation_settings, profile_stats, None)

        # Validate RO-Crate against the profile and get the validation result
        result: ValidationResult = report_layout.live(
            lambda: services.validate(
                validation_settings,
                subscribers=[report_layout.progress_monitor]
            )
        )

        # Print the validation result
        if not result.passed():
            if not details and enable_pager:
                details = get_single_char(console, choices=['y', 'n'],
                                          message="[bold] > Do you want to see the validation details? ([magenta]y/n[/magenta]): [/bold]")
            if details == "y" or details:
                report_layout.show_validation_details(pager, enable_pager=enable_pager)

        if output_file:
            # Print the validation report to a file
            if format == "json":
                with open(output_file, "w") as f:
                    f.write(result.to_json())
            elif format == "text":
                with open(output_file, "w") as f:
                    c = Console(file=f, color_system=None)
                    c.print(report_layout.layout)
                    report_layout.console = c
                    report_layout.show_validation_details(pager, enable_pager=False)

        # using ctx.exit seems to raise an Exception that gets caught below,
        # so we use sys.exit instead.
        sys.exit(0 if result.passed(LevelCollection.get(requirement_severity).severity) else 1)
    except Exception as e:
        handle_error(e, console)


def multiple_choice(console: Console,
                    choices: list[str],
                    title: str = "Main Menu",
                    padding=(1, 2)) -> str:
    """
    Display a multiple choice menu
    """
    table = Table(title=title, title_justify="left")
    table.add_column("#", justify="center", style="bold cyan", no_wrap=True)
    table.add_column("Option", justify="left", style="magenta")

    for index, choice in enumerate(choices, start=1):
        table.add_row(str(index), choice)

    if padding:
        console.print(Padding(Align(table, align="left"), padding))
    else:
        console.print(table)

    # Build the prompt text
    prompt_text = "[bold] > Please select a profile (enter the number)[/bold]"
    # console_width = console.size.width
    # padding = (console_width - len(prompt_text)) // 2
    # centered_prompt_text = " " * padding + prompt_text

    # Get the selected option
    selected_option = Prompt.ask(prompt_text,
                                 choices=[str(i) for i in range(1, len(choices) + 1)])
    return selected_option


class ProgressMonitor(Subscriber):

    PROFILE_VALIDATION = "Profiles"
    REQUIREMENT_VALIDATION = "Requirements"
    REQUIREMENT_CHECK_VALIDATION = "Requirements Checks"

    def __init__(self, layout: ValidationReportLayout, stats: dict):
        self.__progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            expand=True)
        self._stats = stats
        self.profile_validation = self.progress.add_task(
            self.PROFILE_VALIDATION, total=len(stats.get("profiles")))
        self.requirement_validation = self.progress.add_task(
            self.REQUIREMENT_VALIDATION, total=stats.get("total_requirements"))
        self.requirement_check_validation = self.progress.add_task(
            self.REQUIREMENT_CHECK_VALIDATION, total=stats.get("total_checks"))
        self.__layout = layout
        super().__init__("ProgressMonitor")

    def start(self):
        self.progress.start()

    def stop(self):
        self.progress.stop()

    @property
    def layout(self) -> ValidationReportLayout:
        return self.__layout

    @property
    def progress(self) -> Progress:
        return self.__progress

    def update(self, event: Event):
        # logger.debug("Event: %s", event.event_type)
        if event.event_type == EventType.PROFILE_VALIDATION_START:
            logger.debug("Profile validation start: %s", event.profile.identifier)
        elif event.event_type == EventType.REQUIREMENT_VALIDATION_START:
            logger.debug("Requirement validation start")
        elif event.event_type == EventType.REQUIREMENT_CHECK_VALIDATION_START:
            logger.debug("Requirement check validation start")
        elif event.event_type == EventType.REQUIREMENT_CHECK_VALIDATION_END:
            if not event.requirement_check.requirement.hidden:
                self.progress.update(task_id=self.requirement_check_validation, advance=1)
                if event.validation_result is not None:
                    if event.validation_result:
                        self._stats["passed_checks"].append(event.requirement_check)
                    else:
                        self._stats["failed_checks"].append(event.requirement_check)
                    self.layout.update(self._stats)
        elif event.event_type == EventType.REQUIREMENT_VALIDATION_END:
            if not event.requirement.hidden:
                self.progress.update(task_id=self.requirement_validation, advance=1)
                if event.validation_result:
                    self._stats["passed_requirements"].append(event.requirement)
                else:
                    self._stats["failed_requirements"].append(event.requirement)
                self.layout.update(self._stats)
        elif event.event_type == EventType.PROFILE_VALIDATION_END:
            self.progress.update(task_id=self.profile_validation, advance=1)
        elif event.event_type == EventType.VALIDATION_END:
            self.layout.set_overall_result(event.validation_result)


class ValidationReportLayout(Layout):

    def __init__(self, console: Console, validation_settings: dict, profile_stats: dict, result: ValidationResult):
        super().__init__()
        self.console = console
        self.validation_settings = validation_settings
        self.profile_stats = profile_stats
        self.result = result
        self.__layout = None
        self._validation_checks_progress = None
        self.__progress_monitor = None
        self.requirement_checks_container_layout = None
        self.passed_checks = None
        self.failed_checks = None
        self.report_details_container = None

    @property
    def layout(self):
        if not self.__layout:
            self.__init_layout__()
        return self.__layout

    @property
    def validation_checks_progress(self):
        return self._validation_checks_progress

    @property
    def progress_monitor(self) -> ProgressMonitor:
        if not self.__progress_monitor:
            self.__progress_monitor = ProgressMonitor(self, self.profile_stats)
        return self.__progress_monitor

    def live(self, update_callable: callable) -> any:
        assert update_callable, "Update callable must be provided"
        # Start live rendering
        result = None
        with Live(self.layout, console=self.console, refresh_per_second=10, transient=False):
            result = update_callable()
        return result

    def __init_layout__(self):

        # Get the validation settings
        settings = self.validation_settings

        # Set the console height
        self.console.height = 31

        # Create the layout of the base info of the validation report
        severity_color = get_severity_color(Severity.get(settings["requirement_severity"]))
        base_info_layout = Layout(
            Align(
                f"\n[bold cyan]RO-Crate:[/bold cyan] [bold]{URI(settings['data_path']).uri}[/bold]"
                f"\n[bold cyan]Target Profile:[/bold cyan][bold magenta] {settings['profile_identifier']}[/bold magenta] { '[italic](autodetected)[/italic]' if settings['profile_autodetected'] else ''}"
                f"\n[bold cyan]Validation Severity:[/bold cyan] [bold {severity_color}]{settings['requirement_severity']}[/bold {severity_color}]",
                style="white", align="left"),
            name="Base Info", size=5)
        #
        self.passed_checks = Layout(name="PASSED")
        self.failed_checks = Layout(name="FAILED")
        # Create the layout of the requirement checks section
        validated_checks_container = Layout(name="Requirement Checks Validated")
        validated_checks_container.split_row(
            self.passed_checks,
            self.failed_checks
        )

        # Create the layout of the requirement checks section
        self.requirement_checks_by_severity_container_layout = Layout(name="Requirement Checks Validation", size=5)
        self.requirement_checks_by_severity_container_layout.split_row(
            Layout(name="required"),
            Layout(name="recommended"),
            Layout(name="optional")
        )

        # Create the layout of the requirement checks section
        requirement_checks_container_layout = Layout(name="Requirement Checks")
        requirement_checks_container_layout.split_column(
            self.requirement_checks_by_severity_container_layout,
            validated_checks_container
        )

        # Create the layout of the validation checks progress
        self._validation_checks_progress = Layout(
            Panel(Align(self.progress_monitor.progress, align="center"),
                  border_style="white", padding=(0, 1), title="Overall Progress"),
            name="Validation Progress", size=5)

        # Create the layout of the report container
        report_container_layout = Layout(name="Report Container Layout")
        report_container_layout.split_column(
            base_info_layout,
            Layout(Panel(requirement_checks_container_layout,
                   title="[bold]Requirements Checks Validation[/bold]", border_style="white", padding=(1, 1))),
            self._validation_checks_progress
        )

        # Update the layout with the profile stats
        self.update(self.profile_stats)

        # Create the main layout
        self.checks_stats_layout = Layout(
            Panel(report_container_layout, title=f"[bold]- Validation Report -[/bold]",
                  border_style="cyan", title_align="center", padding=(1, 2)))

        # Create the overall result layout
        self.overall_result = Layout(
            Padding(Rule(f"\n[italic][cyan]Validating ROCrate...[/cyan][/italic]"), (1, 1)), size=3)

        group_layout = Layout()
        group_layout.add_split(self.checks_stats_layout)
        group_layout.add_split(self.overall_result)

        self.__layout = Padding(group_layout, (1, 1))

    def update(self, profile_stats: dict = None):
        assert profile_stats, "Profile stats must be provided"
        self.profile_stats = profile_stats
        self.requirement_checks_by_severity_container_layout["required"].update(
            Panel(
                Align(
                    str(profile_stats['check_count_by_severity'][Severity.REQUIRED]) if profile_stats else "0",
                    align="center"
                ),
                padding=(1, 1),
                title="Severity: REQUIRED",
                title_align="center",
                border_style="RED"
            )
        )
        self.requirement_checks_by_severity_container_layout["recommended"].update(
            Panel(
                Align(
                    str(profile_stats['check_count_by_severity'][Severity.RECOMMENDED]) if profile_stats else "0",
                    align="center"
                ),
                padding=(1, 1),
                title="Severity: RECOMMENDED",
                title_align="center",
                border_style="orange1"
            )
        )
        self.requirement_checks_by_severity_container_layout["optional"].update(
            Panel(
                Align(
                    str(profile_stats['check_count_by_severity'][Severity.OPTIONAL]) if profile_stats else "0",
                    align="center"
                ),
                padding=(1, 1),
                title="Severity: OPTIONAL",
                title_align="center",
                border_style="yellow"
            )
        )

        self.passed_checks.update(
            Panel(
                Align(
                    str(len(self.profile_stats["passed_checks"])),
                    align="center"
                ),
                padding=(1, 1),
                title="PASSED Checks",
                title_align="center",
                border_style="green"
            )
        )

        self.failed_checks.update(
            Panel(
                Align(
                    str(len(self.profile_stats["failed_checks"])),
                    align="center"
                ),
                padding=(1, 1),
                title="FAILED Checks",
                title_align="center",
                border_style="red"
            )
        )

    def set_overall_result(self, result: ValidationResult):
        assert result, "Validation result must be provided"
        self.result = result
        if result.passed():
            self.overall_result.update(
                Padding(Rule(f"[bold][[green]OK[/green]] RO-Crate is [green]valid[/green] !!![/bold]\n\n",
                             style="bold green"), (1, 1)))
        else:
            self.overall_result.update(
                Padding(Rule(f"[bold][[red]FAILED[/red]] RO-Crate is [red]not valid[/red] !!![/bold]\n",
                             style="bold red"), (1, 1)))

    def show_validation_details(self, pager: Pager, enable_pager: bool = True):
        """
        Print the validation result
        """
        if not self.result:
            raise ValueError("Validation result is not available")

        # init references to the console, result and severity
        console = self.console
        result = self.result

        logger.debug("Validation failed: %s", result.failed_requirements)

        # Print validation details
        with console.pager(pager=pager, styles=not console.no_color) if enable_pager else console:
            # Print the list of failed requirements
            console.print(
                Padding("\n[bold]The following requirements have not meet: [/bold]", (0, 0)), style="white")
            for requirement in sorted(result.failed_requirements,
                                      key=lambda x: (-x.severity.value, x)):
                issue_color = get_severity_color(requirement.severity)
                console.print(
                    Align(f"\n [severity: [{issue_color}]{requirement.severity.name}[/{issue_color}], "
                          f"profile: [magenta bold]{requirement.profile.name }[/magenta bold]]", align="right")
                )
                console.print(
                    f"  [bold][cyan][{requirement.order_number}] [u]{Markdown(requirement.name).markup}[/u][/cyan][/bold]",
                    style="white",
                )
                console.print(Padding(Markdown(requirement.description), (1, 7)))
                console.print(Padding("[white bold u]  Failed checks  [/white bold u]\n",
                                      (0, 8)), style="white bold")

                for check in sorted(result.get_failed_checks_by_requirement(requirement),
                                    key=lambda x: (-x.severity.value, x)):
                    issue_color = get_severity_color(check.level.severity)
                    console.print(
                        Padding(f"[bold][{issue_color}][{check.identifier.center(16)}][/{issue_color}]  [magenta]{check.name}[/magenta][/bold]:", (0, 7)), style="white bold")
                    console.print(Padding(Markdown(check.description), (0, 27)))
                    console.print(Padding("[u] Detected issues [/u]", (0, 8)), style="white bold")
                    for issue in sorted(result.get_issues_by_check(check),
                                        key=lambda x: (-x.severity.value, x)):
                        path = ""
                        if issue.resultPath and issue.value:
                            path = f" of [yellow]{issue.resultPath}[/yellow]"
                        if issue.value:
                            if issue.resultPath:
                                path += "="
                            path += f"\"[green]{issue.value}[/green]\" "  # keep the ending space
                        if issue.focusNode:
                            path = f"{path} on [cyan]<{issue.focusNode}>[/cyan]"
                        console.print(
                            Padding(f"- [[red]Violation[/red]{path}]: "
                                    f"{Markdown(issue.message).markup}", (0, 9)), style="white")
                    console.print("\n", style="white")


def __compute_profile_stats__(validation_settings: dict):
    """
    Compute the statistics of the profile
    """
    profiles = services.get_profiles(validation_settings.get("profiles_path"))
    profile = services.get_profile(validation_settings.get("profiles_path"),
                                   validation_settings.get("profile_identifier"))
    severity_validation = Severity.get(validation_settings.get("requirement_severity"))
    profiles = [profile]

    if validation_settings.get("inherit_profiles"):
        profiles.extend(profile.inherited_profiles)

    total_requirements = 0
    total_checks = 0
    requirement_count_by_severity = {}
    check_count_by_severity = {}

    for profile in profiles:
        for requirement in profile.requirements:
            if requirement.hidden:
                continue

            severity = requirement.severity

            # Count the number of requirements by severity
            if severity not in requirement_count_by_severity:
                requirement_count_by_severity[severity] = 0

            if severity_validation <= severity:
                requirement_count_by_severity[severity] += 1
                total_requirements += 1

            # Count the number of checks by severity
            if severity not in check_count_by_severity:
                check_count_by_severity[severity] = 0
            if severity_validation <= severity:
                num_checks = len(
                    requirement.get_checks_by_level(LevelCollection.get(severity.name)))
                check_count_by_severity[severity] += num_checks
                total_checks += num_checks

    return {
        "profile": profile,
        "profiles": profiles,
        "requirement_count_by_severity": requirement_count_by_severity,
        "check_count_by_severity": check_count_by_severity,
        "total_requirements": total_requirements,
        "total_checks": total_checks,
        "failed_requirements": [],
        "failed_checks": [],
        "passed_requirements": [],
        "passed_checks": []
    }
