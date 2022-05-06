from typing import Callable
from getpass import getpass
from sys import exit, stderr
from colorama import Fore

from .validator import ensure_type


def better_input(
    prompt: str,
    optional: bool = False,
    attempts: int = 3,
    validator: Callable | None = None,
    password: bool = False,
) -> str | None:
    """
    A better input function that can be used to get input from the user.
    :param prompt: The prompt to display to the user.
    :param optional: Whether the input is optional.
    :param attempts: The max number of attempts the user will be able to provide input.
    :param validator: The validator to use to validate the input. This function must return True if the input is valid, else return an error message.
    :return: The input from the user if it was valid otherwise None.
    """

    ensure_type(prompt, str, "prompt", "string")
    ensure_type(optional, bool, "optional", "boolean")
    ensure_type(attempts, int, "attempts", "integer")
    ensure_type(validator, Callable | None, "validator", "callable or None")
    ensure_type(password, bool, "password", "boolean")

    if validator == None:
        def validator(x): return True

    for _ in range(attempts):
        user_input = getpass(prompt) if password else input(prompt)
        valid_input = validator(user_input)

        # TODO: What if the validator is None and the user inputs nothing but optional is False

        if valid_input != True and optional == False:
            print(
                f"{Fore.RED}{valid_input if type(valid_input) == str else 'Invalid input!'}{Fore.RESET}",
                file=stderr,
                end="\n\n"
            )
            continue

        return user_input

    print(f"{Fore.RED}Failed to get a valid input!{Fore.RESET}", file=stderr)

    return None


def pos_int_input(prompt: str, optional: bool = False, attempts: int = 3) -> int | None:
    ret_val = better_input(prompt, optional, attempts, lambda x: int(x) if x.isdigit() and int(x) >= 0 else "Input must be a positive integer!")
    return int(ret_val) if ret_val != None else None


def confirm(prompt: str, loose: bool = False):
    """
    Returns true if user inputs 'y' or 'Y' after the prompt. If loose is True, the function will return true unless the user inputs 'n' or 'N'
    """
    ensure_type(prompt, str, "prompt", "string")
    ensure_type(loose, bool, "loose", "boolean")

    user_input = input(prompt).lower()
    if not loose:
        return user_input == 'y'
    else:
        return not user_input == 'n'
