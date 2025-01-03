import warnings
from typing import Any, Dict, List, Optional, Tuple, Union


class ValidatedEmail:
    """The validate_email function returns objects of this type holding the normalized form of the email address
    and other information."""

    """The email address that was passed to validate_email. (If passed as bytes, this will be a string.)"""
    original: str

    """The normalized email address, which should always be used in preference to the original address.
    The normalized address converts an IDNA ASCII domain name to Unicode, if possible, and performs
    Unicode normalization on the local part and on the domain (if originally Unicode). It is the
    concatenation of the local_part and domain attributes, separated by an @-sign."""
    normalized: str

    """The local part of the email address after Unicode normalization."""
    local_part: str

    """The domain part of the email address after Unicode normalization or conversion to
    Unicode from IDNA ascii."""
    domain: str

    """If the domain part is a domain literal, the IPv4Address or IPv6Address object."""
    domain_address: object

    """If not None, a form of the email address that uses 7-bit ASCII characters only."""
    ascii_email: Optional[str]

    """If not None, the local part of the email address using 7-bit ASCII characters only."""
    ascii_local_part: Optional[str]

    """A form of the domain name that uses 7-bit ASCII characters only."""
    ascii_domain: str

    """If True, the SMTPUTF8 feature of your mail relay will be required to transmit messages
    to this address. This flag is True just when ascii_local_part is missing. Otherwise it
    is False."""
    smtputf8: bool

    """If a deliverability check is performed and if it succeeds, a list of (priority, domain)
    tuples of MX records specified in the DNS for the domain."""
    mx: List[Tuple[int, str]]

    """If no MX records are actually specified in DNS and instead are inferred, through an obsolete
    mechanism, from A or AAAA records, the value is the type of DNS record used instead (`A` or `AAAA`)."""
    mx_fallback_type: Optional[str]

    """The display name in the original input text, unquoted and unescaped, or None."""
    display_name: Optional[str]

    def __repr__(self) -> str:
        return f"<ValidatedEmail {self.normalized}>"

    """For backwards compatibility, support old field names."""
    def __getattr__(self, key: str) -> str:
        if key == "original_email":
            return self.original
        if key == "email":
            return self.normalized
        raise AttributeError(key)

    @property
    def email(self) -> str:
        warnings.warn("ValidatedEmail.email is deprecated and will be removed, use ValidatedEmail.normalized instead", DeprecationWarning)
        return self.normalized

    """For backwards compatibility, some fields are also exposed through a dict-like interface. Note
    that some of the names changed when they became attributes."""
    def __getitem__(self, key: str) -> Union[Optional[str], bool, List[Tuple[int, str]]]:
        warnings.warn("dict-like access to the return value of validate_email is deprecated and may not be supported in the future.", DeprecationWarning, stacklevel=2)
        if key == "email":
            return self.normalized
        if key == "email_ascii":
            return self.ascii_email
        if key == "local":
            return self.local_part
        if key == "domain":
            return self.ascii_domain
        if key == "domain_i18n":
            return self.domain
        if key == "smtputf8":
            return self.smtputf8
        if key == "mx":
            return self.mx
        if key == "mx-fallback":
            return self.mx_fallback_type
        raise KeyError()

    """Tests use this."""
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValidatedEmail):
            return False
        return (
            self.normalized == other.normalized
            and self.local_part == other.local_part
            and self.domain == other.domain
            and getattr(self, 'ascii_email', None) == getattr(other, 'ascii_email', None)
            and getattr(self, 'ascii_local_part', None) == getattr(other, 'ascii_local_part', None)
            and getattr(self, 'ascii_domain', None) == getattr(other, 'ascii_domain', None)
            and self.smtputf8 == other.smtputf8
            and repr(sorted(self.mx) if getattr(self, 'mx', None) else None)
            == repr(sorted(other.mx) if getattr(other, 'mx', None) else None)
            and getattr(self, 'mx_fallback_type', None) == getattr(other, 'mx_fallback_type', None)
            and getattr(self, 'display_name', None) == getattr(other, 'display_name', None)
        )

    """This helps producing the README."""
    def as_constructor(self) -> str:
        return "ValidatedEmail(" \
            + ",".join(f"\n  {key}={repr(getattr(self, key))}"
                       for key in ('normalized', 'local_part', 'domain',
                                   'ascii_email', 'ascii_local_part', 'ascii_domain',
                                   'smtputf8', 'mx', 'mx_fallback_type',
                                   'display_name')
                       if hasattr(self, key)
                       ) \
            + ")"

    """Convenience method for accessing ValidatedEmail as a dict"""
    def as_dict(self) -> Dict[str, Any]:
        d = self.__dict__
        if d.get('domain_address'):
            d['domain_address'] = repr(d['domain_address'])
        return d
