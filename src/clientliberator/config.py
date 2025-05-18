import os
from os import PathLike
from string import Template
import shutil

import jsonschema
import json
from pathlib import Path
from enum import StrEnum
from tempfile import gettempdir

import requests

with open(Path(__file__).resolve().parent / "config.schema.json", "r") as s_f:
	schema = json.load(s_f)
jsonschema.Draft7Validator.check_schema(schema)
validator = jsonschema.Draft7Validator(schema)


def validate_config_file(path: PathLike) -> bool:
	with open(path, "r") as f:
		return validate_config(json.load(f))


def validate_config(config) -> bool:
	if not isinstance(config, dict):
		return False
	if not validator.is_valid(config):
		return False

	return True


class Kind(StrEnum):
	Remote = "provider"
	Local = "path"
	URL = "url"


class Type(StrEnum):
	JavaScript = "js"
	CSS = "css"
	Other = "other"

	@staticmethod
	def from_extension(file: str) -> "Type":
		for ext in Type:
			if file.endswith('.' + ext.value()):
				return ext
		return Type.Other


class Library:
	@staticmethod
	def from_config(config: dict):
		for kind in Kind:
			if kind.value() in config:
				return Library(
					name=config["name"],
					kind=kind,
					source=config[kind],
					*config.get("files", []),
				)
		return Library(
			name=config["name"],
			kind=Kind.Remote,
			source="cdnjs",
			*config.get("files", []),
		)

	def __init__(self, name: str, kind: Kind, source: str, *files: str):
		self.name = name
		self.files: list[str] = list(files)
		self.kind = kind
		self.source = source

	def collect_files(self, output_dir: PathLike):
		"""Collect files from the library and save them to the static directory."""
		dst_folder = Path(output_dir) / self.name
		if not dst_folder.exists():
			os.makedirs(dst_folder)

		if self.kind == Kind.Local:
			for file in self.files:
				src = Path(self.source) / file
				dst = dst_folder / file
				shutil.copy(src, dst)
		elif self.kind == Kind.URL:
			for file in self.files:
				dst = dst_folder / file
				with requests.get(self.source, stream=True) as req:
					if req.status_code == 200:
						with open(dst, "wb") as f:
							for chunk in req.iter_content(chunk_size=8192):
								f.write(chunk)
					else:
						print(f"[ClientLiberator] Failed to download {file} from {self.source} with status code {req.status_code} ({self.name})")
		elif self.kind == Kind.Remote:
			if self.source == "cdnjs":
				for file in self.files:
					dst = dst_folder / file
					with requests.get(f"https://cdnjs.cloudflare.com/ajax/libs/{self.name}/{file}", stream=True) as req:
						if req.status_code == 200:
							with open(dst, "wb") as f:
								for chunk in req.iter_content(chunk_size=8192):
									f.write(chunk)
						else:
							print(f"[ClientLiberator] Failed to download {file} from {self.source} with status code {req.status_code} ({self.name})")
			else:
				raise ValueError(f"Unknown provider: {self.source}")
		else:
			raise ValueError(f"Unknown kind: {self.kind}")


class Collection:
	def __init__(self, name: str, libraries: list[Library], extends: list[str]):
		self.name = name
		self.libraries = libraries
		self.extends = extends

	def __iter__(self):
		return iter(self.libraries)


class Config:
	@staticmethod
	def create_default(path: PathLike):
		default_config = {
			"libraries": []
		}

		with open(path, "w") as f:
			json.dump(default_config, f, indent=4)

	def __init__(self, path: PathLike):
		self.path = Path(path).resolve().absolute()

		self.base_path = self.path.parent.resolve().absolute()

		with open(self.path, "r") as f:
			config_raw = json.load(f)

		if not validate_config(config_raw):
			raise ValueError(f"Invalid config file: {self.path}")
		config: dict = config_raw

		self.static_path: Path = Path(config.get("static_path", "static"))
		if not self.static_path.is_absolute():
			self.static_path = self.base_path / self.static_path
		self.static_path = self.static_path.resolve().absolute()
		if not self.static_path.exists() or not self.static_path.is_dir():
			os.mkdir(self.static_path)

		self.output_path: Path = Path(config.get("output", "clientliberator"))
		if not self.output_path.is_absolute():
			self.output_path = self.static_path / self.output_path
		self.output_path = self.output_path.resolve().absolute()
		if self.static_path not in self.output_path.parents:
			raise ValueError(f"Output path {self.output_path} must be inside the static path {self.static_path}")

		self.output_dir: str = config.get("output", "clientliberator")
		if self.output_dir.startswith("./"):
			self.output_dir = self.output_dir[2:]

		if "libraries" in config:
			self.collections: dict[str, Collection] = {
				"single": Collection("single", [Library.from_config(cfg) for cfg in config["libraries"]], []),
			}
			self.default_collection = "single"
		else:
			self.collections: dict[str, Collection] = {}
			for name, cfg in config["collections"].items():
				self.collections[name] = Collection(name, [Library.from_config(lib) for lib in cfg["libraries"]], cfg.get("extends", []))
			self.default_collection = config.get("default_collection", "default")

		self.tempdir_path = Template(config.get("tempDirectory", "$TEMP/clientliberator-$RAND")).substitute(
			TEMP=gettempdir(),
			RAND=os.urandom(8).hex(),
		)

