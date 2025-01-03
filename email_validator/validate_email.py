from typing import Optional, Union, TYPE_CHECKING
import unicodedata

from .exceptions import EmailSyntaxError
from .types import ValidatedEmail
from .syntax import split_email, validate_email_local_part, validate_email_domain_name, validate_email_domain_literal, validate_email_length
from .rfc_constants import CASE_INSENSITIVE_MAILBOX_NAMES

if TYPE_CHECKING:
    import dns.resolver
    _Resolver = dns.resolver.Resolver
else:
    _Resolver = object


def validate_email(
    email: Union[str, bytes],
    /,  # prior arguments are positional-only
    *,  # subsequent arguments are keyword-only
    allow_smtputf8: Optional[bool] = None,
    allow_empty_local: Optional[bool] = None,
    allow_quoted_local: Optional[bool] = None,
    allow_domain_literal: Optional[bool] = None,
    allow_display_name: Optional[bool] = None,
    check_deliverability: Optional[bool] = None,
    test_environment: Optional[bool] = None,
    globally_deliverable: Optional[bool] = None,
    timeout: Optional[int] = None,
    dns_resolver: Optional[_Resolver] = None
) -> ValidatedEmail:
    """
    Given an email address, and some options, returns a ValidatedEmail instance
    with information about the address if it is valid or, if the address is not
    valid, raises an EmailNotValidError. This is the main function of the module.
    """

    # Fill in default values of arguments.
    from . import ALLOW_SMTPUTF8, ALLOW_EMPTY_LOCAL, ALLOW_QUOTED_LOCAL, ALLOW_DOMAIN_LITERAL, ALLOW_DISPLAY_NAME, \
        GLOBALLY_DELIVERABLE, CHECK_DELIVERABILITY, TEST_ENVIRONMENT, DEFAULT_TIMEOUT
    if allow_smtputf8 is None:
        allow_smtputf8 = ALLOW_SMTPUTF8
    if allow_empty_local is None:
        allow_empty_local = ALLOW_EMPTY_LOCAL
    if allow_quoted_local is None:
        allow_quoted_local = ALLOW_QUOTED_LOCAL
    if allow_domain_literal is None:
        allow_domain_literal = ALLOW_DOMAIN_LITERAL
    if allow_display_name is None:
        allow_display_name = ALLOW_DISPLAY_NAME
    if check_deliverability is None:
        check_deliverability = CHECK_DELIVERABILITY
    if test_environment is None:
        test_environment = TEST_ENVIRONMENT
    if globally_deliverable is None:
        globally_deliverable = GLOBALLY_DELIVERABLE
    if timeout is None and dns_resolver is None:
        timeout = DEFAULT_TIMEOUT

    # Allow email to be a str or bytes instance. If bytes,
    # it must be ASCII because that's how the bytes work
    # on the wire with SMTP.
    if not isinstance(email, str):
        try:
            email = email.decode("ascii")
        except ValueError as e:
            raise EmailSyntaxError("The email address is not valid ASCII.") from e

    # Split the address into the display name (or None), the local part
    # (before the @-sign), and the domain part (after the @-sign).
    # Normally, there is only one @-sign. But the awkward "quoted string"
    # local part form (RFC 5321 4.1.2) allows @-signs in the local
    # part if the local part is quoted.
    display_name, local_part, domain_part, is_quoted_local_part \
        = split_email(email)

    if display_name:
        # UTS #39 3.3 Email Security Profiles for Identifiers requires
        # display names (incorrectly called "quoted-string-part" there)
        # to be NFC normalized. Since these are not a part of what we
        # are really validating, we won't check that the input was NFC
        # normalized, but we'll normalize in output.
        display_name = unicodedata.normalize("NFC", display_name)

    # Collect return values in this instance.
    ret = ValidatedEmail()
    ret.original = ((local_part if not is_quoted_local_part
                    else ('"' + local_part + '"'))
                    + "@" + domain_part)  # drop the display name, if any, for email length tests at the end
    ret.display_name = display_name

    # Validate the email address's local part syntax and get a normalized form.
    # If the original address was quoted and the decoded local part is a valid
    # unquoted local part, then we'll get back a normalized (unescaped) local
    # part.
    local_part_info = validate_email_local_part(local_part,
                                                allow_smtputf8=allow_smtputf8,
                                                allow_empty_local=allow_empty_local,
                                                quoted_local_part=is_quoted_local_part)
    ret.local_part = local_part_info["local_part"]
    ret.ascii_local_part = local_part_info["ascii_local_part"]
    ret.smtputf8 = local_part_info["smtputf8"]

    # RFC 6532 section 3.1 says that Unicode NFC normalization should be applied,
    # so we'll return the NFC-normalized local part. Since the caller may use that
    # string in place of the original string, ensure it is also valid.
    #
    # UTS #39 3.3 Email Security Profiles for Identifiers requires local parts
    # to be NFKC normalized, which loses some information in characters that can
    # be decomposed. We might want to consider applying NFKC normalization, but
    # we can't make the change easily because it would break database lookups
    # for any caller that put a normalized address from a previous version of
    # this library. (UTS #39 seems to require that the *input* be NKFC normalized
    # and has other requirements that are hard to check without additional Unicode
    # data, and I don't know whether the rules really apply in the wild.)
    normalized_local_part = unicodedata.normalize("NFC", ret.local_part)
    if normalized_local_part != ret.local_part:
        try:
            validate_email_local_part(normalized_local_part,
                                      allow_smtputf8=allow_smtputf8,
                                      allow_empty_local=allow_empty_local,
                                      quoted_local_part=is_quoted_local_part)
        except EmailSyntaxError as e:
            raise EmailSyntaxError("After Unicode normalization: " + str(e)) from e
        ret.local_part = normalized_local_part

    # If a quoted local part isn't allowed but is present, now raise an exception.
    # This is done after any exceptions raised by validate_email_local_part so
    # that mandatory checks have highest precedence.
    if is_quoted_local_part and not allow_quoted_local:
        raise EmailSyntaxError("Quoting the part before the @-sign is not allowed here.")

    # Some local parts are required to be case-insensitive, so we should normalize
    # to lowercase.
    # RFC 2142
    if ret.ascii_local_part is not None \
       and ret.ascii_local_part.lower() in CASE_INSENSITIVE_MAILBOX_NAMES \
       and ret.local_part is not None:
        ret.ascii_local_part = ret.ascii_local_part.lower()
        ret.local_part = ret.local_part.lower()

    # Validate the email address's domain part syntax and get a normalized form.
    is_domain_literal = False
    if len(domain_part) == 0:
        raise EmailSyntaxError("There must be something after the @-sign.")

    elif domain_part.startswith("[") and domain_part.endswith("]"):
        # Parse the address in the domain literal and get back a normalized domain.
        domain_literal_info = validate_email_domain_literal(domain_part[1:-1])
        if not allow_domain_literal:
            raise EmailSyntaxError("A bracketed IP address after the @-sign is not allowed here.")
        ret.domain = domain_literal_info["domain"]
        ret.ascii_domain = domain_literal_info["domain"]  # Domain literals are always ASCII.
        ret.domain_address = domain_literal_info["domain_address"]
        is_domain_literal = True  # Prevent deliverability checks.

    else:
        # Check the syntax of the domain and get back a normalized
        # internationalized and ASCII form.
        domain_name_info = validate_email_domain_name(domain_part, test_environment=test_environment, globally_deliverable=globally_deliverable)
        ret.domain = domain_name_info["domain"]
        ret.ascii_domain = domain_name_info["ascii_domain"]

    # Construct the complete normalized form.
    ret.normalized = ret.local_part + "@" + ret.domain

    # If the email address has an ASCII form, add it.
    if not ret.smtputf8:
        if not ret.ascii_domain:
            raise Exception("Missing ASCII domain.")
        ret.ascii_email = (ret.ascii_local_part or "") + "@" + ret.ascii_domain
    else:
        ret.ascii_email = None

    # Check the length of the address.
    validate_email_length(ret)

    # Check that a display name is permitted. It's the last syntax check
    # because we always check against optional parsing features last.
    if display_name is not None and not allow_display_name:
        raise EmailSyntaxError("A display name and angle brackets around the email address are not permitted here.")

    if check_deliverability and not test_environment:
        # Validate the email address's deliverability using DNS
        # and update the returned ValidatedEmail object with metadata.

        if is_domain_literal:
            # There is nothing to check --- skip deliverability checks.
            return ret

        # Lazy load `deliverability` as it is slow to import (due to dns.resolver)
        from .deliverability import validate_email_deliverability
        deliverability_info = validate_email_deliverability(
            ret.ascii_domain, ret.domain, timeout, dns_resolver
        )
        mx = deliverability_info.get("mx")
        if mx is not None:
            ret.mx = mx
        ret.mx_fallback_type = deliverability_info.get("mx_fallback_type")

    return ret
