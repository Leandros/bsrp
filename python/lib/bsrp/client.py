from typing import Tuple

from .utils import (
    SafetyException,
    _calculate_M,
    _calculate_x,
    _generate_random_bytes,
    _get_srp_generator,
    _get_srp_prime,
    _Hash,
    _pad,
    _to_int,
)


class EvidenceException(Exception):
    """
    Exception raised when server evidence key does not match.
    """
    pass


def generate_a_pair() -> Tuple[int, int]:
    """
    Generate private ephemeral a and public key A.

    Returns:
        Tuple (private a (int), public A (int))
    """
    prime = _get_srp_prime()
    generator = _get_srp_generator()

    a = _to_int(_generate_random_bytes(32))  # RFC-5054 reccomends 256 bits

    A = pow(generator, a, prime)

    return a, A


def process_challenge(
    identity: str,
    password: str,
    salt: bytes,
    a: int,
    A: int,
    B: int,
) -> Tuple[bytes, bytes]:
    """
    Takes in salt and public value B to respond to SRP challenge with
    message M. Also returns session key for later authentication that
    the server is legit.

    Args:
        identity (str): the identity to process
        password (str): the password to process
        a        (int): the ephemeral value a generated by the client
        A        (int): the public value A generated by the client
        B        (int): the public value B from the server


    Returns:
        Tuple (message (bytes), session_key (bytes))

    Raises:
        SafetyException: if fails to pass SRP-6a safety checks
    """
    prime = _get_srp_prime()

    width = prime.bit_length()

    generator = _get_srp_generator()
    padded_generator = _pad(generator, width)

    padded_A = _pad(A, width)
    padded_B = _pad(B, width)

    # u - random scrambling param
    u = _to_int(_Hash(padded_A, padded_B))

    # x - private key
    x = _calculate_x(salt, identity, password)

    # k - multiplier
    k = _to_int(_Hash(prime, padded_generator))

    # SRP-6a safety checks
    if B == 0:
        raise SafetyException("Public value B is 0. Auth Failed.")

    if u == 0:
        raise SafetyException("Scrambler u is 0. Auth Failed.")

    # Premaster secret, S = (B - k*(generator^x)) ^ (a + u*x)
    t1 = B - k * pow(generator, x, prime)
    t2 = a + u * x

    # Calculate shared session key
    S = pow(t1, t2, prime)
    session_key = _Hash(S)

    # Shared message to server
    M = _calculate_M(
        generator,
        prime,
        identity,
        salt,
        A,
        B,
        session_key,
    )

    return M, session_key


def verify_session(
    A: int,
    M: bytes,
    session_key: bytes,
    server_H_AMK: bytes,
) -> bytes:
    """
    Verify session with server evidence key H_AMK.

    Args:
        A              (int): the public A value generated by the client
        M            (bytes): the message the client sends to the server
        session_key  (bytes): the strong private session key generated by the client
        server_H_AMK (bytes): the evidence key returned by the server
    """
    client_H_AMK = _Hash(A, M, session_key)

    if client_H_AMK != server_H_AMK:
        raise EvidenceException("Evidence keys do not match. Auth Failed.")

    return client_H_AMK
