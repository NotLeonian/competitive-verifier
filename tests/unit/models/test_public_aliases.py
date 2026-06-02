from competitive_verifier.models import (
    AdditionalSource,
    AddtionalSource,
    VerifcationTimeoutError,
    VerificationTimeoutError,
)
from competitive_verifier.models.file import AddtionalSource as FileAddtionalSource
from competitive_verifier.models.verification import (
    VerifcationTimeoutError as ModuleVerifcationTimeoutError,
)


def test_legacy_public_aliases():
    assert AddtionalSource is AdditionalSource
    assert FileAddtionalSource is AdditionalSource
    assert VerifcationTimeoutError is VerificationTimeoutError
    assert ModuleVerifcationTimeoutError is VerificationTimeoutError
