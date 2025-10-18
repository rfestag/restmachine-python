"""
RestMachine CLI for project scaffolding and management.

Provides commands like:
    restmachine new myapp           # Create new project
    restmachine generate model User # Generate model (future)
    restmachine generate controller users # Generate controller (future)
"""

import click
from restmachine.cli.new import new_command


@click.group()
@click.version_option()
def main():
    """RestMachine - CLI for REST applications."""
    pass


# Register commands
main.add_command(new_command, name="new")


if __name__ == "__main__":
    main()
