# Copyright (c) 2024 CRS4
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import re

from rocrate_validator.models import Severity
from tests.ro_crates import WROCNoLicense, WROCMainEntity
from tests.shared import do_entity_test

logger = logging.getLogger(__name__)


def test_wroc_no_license():
    """\
    Test a Workflow RO-Crate where the root data entity has no license.
    """
    do_entity_test(
        WROCNoLicense().wroc_no_license,
        Severity.REQUIRED,
        False,
        ["WROC Root Data Entity Required Properties"],
        [
            "Less than 1 values on <file://.//>-><http://schema.org/license>"
            # TODO: return to message: "The Crate (Root Data Entity) must specify a license, which should be a URL but can also be a string"
            # after https://github.com/linkml/linkml/issues/2417 is fixed
        ],
        profile_identifier="workflow-ro-crate-linkml",
    )


def test_wroc_no_mainentity():
    """\
    Test a Workflow RO-Crate where the root data entity has no mainEntity.
    """
    do_entity_test(
        WROCMainEntity().wroc_no_mainentity,
        Severity.REQUIRED,
        False,
        ["WROC Root Data Entity Required Properties"],
        [
            "The Main Workflow must be specified through a `mainEntity` property in the root data entity"
        ],
        profile_identifier="workflow-ro-crate-linkml",
    )
