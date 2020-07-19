import json
import subprocess

# Print the provided args separated by a space in the given color.
def red(*args):
    print("\033[91m{}\033[00m" .format(' '.join(args)))

def green(*args):
    print("\u001b[32m{}\033[00m" .format(' '.join(args)))

def yellow(*args):
    print("\u001b[33m{}\033[00m" .format(' '.join(args)))

# Returns if the command has a non zero exit code. Used for checking
# if an install command should run or not.
def non_zero_exit_handler(command):
    return subprocess.run(["bash", "-c", command],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode != 0

#Checks if a binary is already installed by querying using "which".
def not_already_installed_handler(binary):
    return non_zero_exit_handler("which " + binary)

# Checks if a file already exists.
def file_not_exists_handler(filename):
    return non_zero_exit_handler("test -f " + filename)

# Checks if a directory already exists.
def directory_not_exists_handler(directory):
    return non_zero_exit_handler("test -d " + directory)

# Run the provided command and return if it was successful or not.
def command_handler(command):
    thing = subprocess.run(["bash", "-c", command])
    return thing.returncode == 0

# Helper function for returning a handler for an instruction.
def lookup_handler(handlers, stanza):
    for key, handler in handlers.items():
        if key in stanza:
            return lambda: handler(stanza[key])
    return None

# Return the handler for a given check instruction.
def get_check_handler(check_stanza):
    handlers = {
        "non-zero-exit": non_zero_exit_handler,
        "not-already-installed": not_already_installed_handler,
        "file-not-exists": file_not_exists_handler,
        "directory-not-exists": directory_not_exists_handler,
    }
    return lookup_handler(handlers, check_stanza)

# Return the handler for a given install instruction.
def get_install_handler(install_stanza):
    handlers = {
        "command": command_handler,
    }
    return lookup_handler(handlers, install_stanza)

# The "homebrew" macro uses homebrew to install a package if it
# doesn't exist.
def expand_homebrew_macro(instruction):
    if "homebrew" not in instruction:
        return instruction

    binary = instruction["homebrew"]
    return {
        "name": "Install " + binary,
        "check": {
            "non-zero-exit": "brew list " + binary
        },
        "install": {
            "command": "brew install " + binary
        }
    }

# Manual instructions are always skipped, they are just here as
# a reminder that manual action is required.
def expand_manual_macro(instruction):
    if "manual" not in instruction:
        return instruction

    name = instruction["manual"]
    return {
        "name": "[Manual Action Required] " + name,
        "check": {
            "non-zero-exit": "echo"
        },
    }


# Downloads a file using cURL to the specified location.
def expand_download_file_macro(instruction):
    if "download-file" not in instruction:
        return instruction

    name = instruction["name"]
    to = instruction["to"]
    path = instruction["download-file"]
    return {
        "name": name,
        "check": {
            "file-not-exists": to
        },
        "install": {
            "command": "curl -L " + path + " -o " + to
        }
    }

# Some instructions are actually "macro" instructions. This function
# expands these macro instructions into full instructions, or otherwise
# just echos the instruction back if it isnt a macro.
def maybe_expand_macro(instruction):
    expanders = [
            expand_homebrew_macro,
            expand_manual_macro,
            expand_download_file_macro,
    ]
    for expander in expanders:
        instruction = expander(instruction)
    return instruction

instructions = json.load(open("./instructions.json"))["steps"]
for instruction in instructions:
    instruction = maybe_expand_macro(instruction)
    name = instruction["name"]
    # TODO: Consider running all the checks in parallel and then
    # serializing the install calls.
    should_run = "check" not in instruction or\
                 get_check_handler(instruction["check"])()
    if should_run:
        success = get_install_handler(instruction["install"])()
        if not success:
            red("[-]", name, "failed")
        else:
            green("[+]", name, "success")
    else:
        yellow("[~]", "Skipping", name)
