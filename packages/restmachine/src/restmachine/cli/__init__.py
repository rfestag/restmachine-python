"""
RestMachine CLI for project scaffolding and management.

Provides commands like:
    restmachine new myapp              # Create new project
    restmachine seed                   # Seed database with fixtures
    restmachine generate scaffold User # Generate complete CRUD scaffold
    restmachine <backend> <command>    # Backend-specific commands (via plugins)
"""

import click
from restmachine.cli.new import new_command
from restmachine.cli.seed import seed_command
from restmachine.cli.generate import generate
from restmachine.cli.plugin_manager import get_plugin_manager


@click.group()
@click.version_option()
def main():
    """RestMachine - CLI for REST applications."""
    pass


# Register core commands
main.add_command(new_command, name="new")
main.add_command(seed_command, name="seed")
main.add_command(generate, name="generate")

# Register plugin commands dynamically
def _register_plugin_commands():
    """Discover and register commands from CLI extension plugins."""
    plugin_manager = get_plugin_manager()

    for extension_name, extension in plugin_manager.list_extensions().items():
        # Register generate subcommands
        generate_commands = extension.get_generate_commands()
        if generate_commands:
            # Add each command from the group to the generate command
            # e.g., `restmachine generate lambda-extension`
            for command in generate_commands.commands.values():
                generate.add_command(command)

        # Register top-level commands
        top_level_commands = extension.get_top_level_commands()
        if top_level_commands:
            # Register the command group under the extension name
            # e.g., `restmachine aws deploy`
            main.add_command(top_level_commands, name=extension_name)


# Register plugins at module load time
_register_plugin_commands()


if __name__ == "__main__":
    main()
