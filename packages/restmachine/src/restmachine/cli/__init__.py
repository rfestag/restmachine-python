"""
RestMachine CLI for project scaffolding and management.

Provides commands like:
    restmachine new myapp           # Create new project
    restmachine seed                # Seed database with fixtures
    restmachine generate model User # Generate model (future)
    restmachine generate controller users # Generate controller (future)
"""

import click
from restmachine.cli.new import new_command
from restmachine.cli.seed import seed_command


@click.group()
@click.version_option()
def main():
    """RestMachine - CLI for REST applications."""
    pass


# Register commands
main.add_command(new_command, name="new")
main.add_command(seed_command, name="seed")


if __name__ == "__main__":
    main()
