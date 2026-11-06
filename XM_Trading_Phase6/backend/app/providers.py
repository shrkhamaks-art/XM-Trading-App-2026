from typing import Protocol

class OtpProvider(Protocol):
    def send_code(self, destination: str, code: str) -> None: ...

class KycProvider(Protocol):
    def create_case(self, user_reference: str) -> str:
        '''Return a provider reference; never accept identity documents in this demo.'''
        ...

class DemoOtpProvider:
    def send_code(self, destination: str, code: str) -> None:
        # Intentionally no external delivery. Development-only caller logs code.
        return None

class UnconfiguredKycProvider:
    def create_case(self, user_reference: str) -> str:
        raise RuntimeError("KYC provider is not configured or approved")
