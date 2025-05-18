import click

from . import __version__


@click.group()
def main():
	pass


@main.command()
def version():
	click.echo(f"ClientLiberator version: {__version__}")


@main.command()
@click.argument(
	"path",
	type=click.Path(exists=True, dir_okay=False, readable=True),
	default="clientliberator.json",
)
def validate(path):
	"""Validate the configuration file."""
	from .config import validate_config_file

	if validate_config_file(path):
		click.echo("Configuration file is valid")
	else:
		click.echo("Configuration file is invalid")


@main.command()
@click.argument(
	"path",
	type=click.Path(exists=True, dir_okay=False, readable=True),
	default="clientliberator.json",
)
def init(path):
	"""Initialize the configuration file."""
	from .config import Config

	Config.create_default(path)
	click.echo(f"Configuration file created at {path}")


@main.command()
@click.argument(
	"path",
	type=click.Path(exists=True, dir_okay=False, readable=True),
	default="clientliberator.json",
)
def build(path):
	"""Build the clientliberator output."""
	from . import ClientLiberator

	clientliberator = ClientLiberator(None, path)
	clientliberator.build()
	click.echo(f"Clientliberator output built at {clientliberator.config.output_path}")
