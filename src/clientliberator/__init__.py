import json
import os.path
import shutil
from collections import Counter
from os import PathLike
from pathlib import Path

import jsonschema


from flask import Flask

from .config import Config, Type, Library, Kind, Collection


__all__ = ["ClientLiberator", "Config", "Type", "Kind", "Library", "Collection"]
__version__ = "0.1.0"


class ClientLiberator:
	def __init__(self, app: Flask | None, config_path: PathLike = "clientliberator.json"):
		conf_path = Path(config_path).resolve().absolute()
		if not conf_path.is_file():
			Config.create_default(conf_path)

		self.config = Config(conf_path)
		self.app = app

	def build(self):
		shutil.rmtree(self.config.output_path, ignore_errors=True)
		os.mkdir(self.config.output_path)
		for lib in self.get_all_libraries():
			lib.collect_files(self.config.output_path)

	def get_all_libraries(self) -> list[Library]:
		"""Get all libraries from the config file. Will return a list of all unqiue libraries in all collections."""
		libraries = []
		for collection in self.config.collections.values():
			libraries.extend(collection.libraries)

		# Remove duplicates
		libraries = list({lib.name: lib for lib in libraries}.values())

		return libraries

	def inject_methods(self):
		"""Inject the methods into the Flask app. This will add a context processor to the app that will inject the HTML into the <head> tag of the page."""
		if self.app is None:
			raise ValueError("Flask app is not set. Please set the app before calling this method.")
		self.app.context_processor(lambda: dict(clientliberator_inject=self.get_html),)

	def get_html(self, collection_name: str | None = None) -> str:
		"""Get the HTML to inject into the <head> tag of the page."""
		if self.app is None:
			raise ValueError("Flask app is not set. Please set the app before calling this method.")

		if collection_name is not None and collection_name not in self.config.collections:
			raise ValueError(f"Collection {collection_name} not found in config file")

		collection = self.config.collections[collection_name or self.config.default_collection]

		libraries = collection.libraries.copy()
		for extend in collection.extends:
			if extend not in self.config.collections:
				raise ValueError(f"Collection {extend} not found in config file")
			libraries.extend(self.config.collections[extend].libraries)

		head_html = "<!-- ClientLiberator Injection -->\n"
		for library in libraries:
			for file in library.files:
				t = Type.from_extension(file)
				ref = self.app.url_for('static', filename=file)
				if t == Type.JavaScript:
					head_html += f'<script src="{ref}"></script>\n'
				elif t == Type.CSS:
					head_html += f'<link rel="stylesheet" href="{ref}">\n'
				else:
					raise ValueError(f"Unknown file type: {file}")
		return head_html + "<!-- End ClientLiberator Injection -->\n"

