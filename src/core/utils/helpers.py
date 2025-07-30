from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from agno.models.openrouter import OpenRouter
from agno.tools.file import FileTools
from agno.workflow.v2.types import StepOutput
from arango import ArangoClient
from arango.database import StandardDatabase
from pydantic import BaseModel

from core.utils.paths import CONFIG_DIR, DATA_DIR

log = logging.getLogger(__name__)


def load_yaml(file, key=None):
    """Loads and parses a YAML file from the CONFIG_DIR.

    Args:
        file (str): The base filename (without extension) of the YAML file to load.
        key (str, optional): Returns only this top-level key from the YAML data.

    Returns:
        dict | Any: Parsed YAML contents, or the sub-dictionary at `key` if specified.
    """
    try:
        # Support both .yaml and .yml extensions
        files = [CONFIG_DIR / f"{file}.yaml", CONFIG_DIR / f"{file}.yml"]
        path = next((p for p in files if p.exists()), None)
        if not path:
            raise FileNotFoundError(
                f"No YAML file found for '{file}' with .yaml or .yml extension."
            )

        with open(path, "r") as f:
            data = yaml.safe_load(f)
            return data[key] if key else data

    except Exception as e:
        log.error(f"Error loading {file}: {e}")


def resolve_model(
    provider: str, model_id: str, temperature: float = 0, reasoning: bool = False
):
    """Returns an LLM client for the given provider, model ID, and config.

    Args:
        provider (str): One of 'openai', 'google', or 'openrouter'.
        model_id (str): Model name or version string for the provider.
        temperature (float, optional): Sampling temperature. Ignored if reasoning=True.
        reasoning (bool, optional): If True, uses deterministic behavior (temp ignored).

    Returns:
        An instance of OpenAIChat, Gemini, or OpenRouter configured accordingly.
    """
    try:
        if provider == "openai":
            if reasoning:
                return OpenAIChat(id=model_id)
            else:
                return OpenAIChat(id=model_id, temperature=temperature)

        elif provider == "google":
            if reasoning:
                return Gemini(id=model_id)
            else:
                return Gemini(id=model_id, temperature=temperature)

        elif provider == "openrouter":
            if reasoning:
                return OpenRouter(id=model_id, api_key=os.getenv("OPENROUTER_API_KEY"))
            else:
                return OpenRouter(
                    id=model_id,
                    api_key=os.getenv("OPENROUTER_API_KEY"),
                    temperature=temperature,
                )
    except Exception as e:
        log.error(f"Error loading LLM provider/model: {e}")


def validate_response(output_content, response_model, savefile=None):
    """Validates structured output against a Pydantic schema and optionally saves it.

    Args:
        output_content (str | dict | BaseModel): The agent response to validate. If a string, it is parsed as JSON.
        response_model (BaseModel): The expected Pydantic schema to validate against.
        savefile (str, optional): If provided, saves validated output to `test_outputs/{savefile}.json`.

    Returns:
        BaseModel | dict | None: A validated instance of `response_model` or raw fallback dict.
    """
    try:
        # Convert to JSON if response not structured (like Google)
        if isinstance(output_content, str):
            output_content = parse_json(output_content)

        # Ensure JSON object is a Pydantic model instance
        if not isinstance(output_content, response_model):
            output_content = response_model(**output_content)

        if savefile:
            output_path = DATA_DIR / f"{savefile}.json"
            with open(output_path, "w") as f:
                json.dump(output_content.model_dump(), f, indent=4)
                log.info(f"Saved structured output to {output_path}")

        return output_content
    except IOError as e:
        log.error(f"Failed to write output file {output_path}: {e}")

    # Handle case if content isn't a Pydantic model
    except AttributeError:
        log.warning("Output content does not have model_dump method.")

        # Fallback: try saving raw content
        try:
            with open(output_path.with_suffix(".raw.json"), "w") as f:
                json.dump(output_content, f, indent=4)
        except Exception:
            log.error("Could not save raw output content.")
            return None


def validate_output(output_content, schema):
    """Validates an agent's structured output against a Pydantic schema.

    Args:
        output_content (str | dict | BaseModel): The structured response from the agent. If a string, it is parsed as JSON.
        schema (type[BaseModel]): The expected Pydantic model class.

    Returns:
        BaseModel: A validated instance of the provided schema.
    """
    try:
        # Convert to JSON if response not structured (like Google)
        if isinstance(output_content, str):
            print(output_content)
            output_content = parse_json(output_content)
            print(output_content)

        # Ensure JSON object is a Pydantic model instance
        if not isinstance(output_content, schema):
            output_content = schema(**output_content)

        return output_content

    # Handle case if content isn't a Pydantic model
    except AttributeError:
        log.warning("Output content does not have model_dump method.")


def parse_json(json_string: str):
    """Attempts to parse a string as JSON, optionally cleaning formatting artifacts.

    Args:
        json_string (str): A raw string potentially containing JSON content.

    Returns:
        dict | list | None: Parsed JSON object (dict or list), or None on failure.
    """
    try:
        # Strip whitespace
        text = json_string.strip()

        # Remove ticks if necessary
        text = text.strip().strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def safe_json(blob: Any) -> Dict[str, Any]:
    """Attempts to return a JSON-compatible dictionary from any input.

    Args:
        blob (Any): A JSON string, dict-like object, or any arbitrary input.

    Returns:
        dict[str, Any]: Parsed dictionary if possible; otherwise an empty dict.
    """
    if not blob:
        return {}
    if isinstance(blob, dict):
        return blob
    if isinstance(blob, (str, bytes, bytearray)):
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            log.debug("Bad JSON blob ignored: %s", blob)
    return {}


def pydantic_to_gemini(output_model: BaseModel) -> str:
    """Serializes a Pydantic model to a compact JSON string for Gemini input.

    Args:
        output_model (BaseModel): A Pydantic model instance.

    Returns:
        str: JSON string representation of the model.
    """
    return json.dumps(output_model.model_dump(), ensure_ascii=False, indent=None)


def get_arango_client() -> ArangoClient:
    """Initializes and returns an ArangoClient using the ARANGO_HOST env variable.

    Returns:
        ArangoClient: An instance configured to connect to the target host.
    """
    host = os.getenv("ARANGO_HOST")
    return ArangoClient(hosts=host)


def get_system_db() -> StandardDatabase:
    """Returns a handle to the _system database.

    Uses ARANGO_USERNAME and ARANGO_PASSWORD environment variables.
    Useful for administrative tasks like creating or deleting databases.

    Returns:
        StandardDatabase: Authenticated connection to the _system database.
    """
    client = get_arango_client()
    username = os.getenv("ARANGO_USERNAME", "root")
    password = os.getenv("ARANGO_PASSWORD")
    return client.db("_system", username=username, password=password)


def get_arango_db() -> StandardDatabase:
    """Returns a handle to the target ArangoDB database specified in ARANGO_DB.

    This function assumes the database already exists. It does not create or delete databases.

    Returns:
        StandardDatabase: Authenticated connection to the target database.
    """
    client = get_arango_client()
    username = os.getenv("ARANGO_USERNAME", "root")
    password = os.getenv("ARANGO_PASSWORD")
    db_name = os.getenv("ARANGO_DB")
    return client.db(db_name, username=username, password=password)


def resolve_api_key(provider: str) -> str | None:
    """Resolves the appropriate API key from the environment based on the LLM provider.

    Args:
        provider (str): Name of the provider (e.g., "openai", "google", etc.)

    Returns:
        str | None: API key if found in environment, otherwise None.
    """
    provider = provider.lower()

    env_keys = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }

    for key, env_var in env_keys.items():
        if key in provider:
            return os.getenv(env_var)
    return None


def save_workflow_output(
    step_output: StepOutput,
    output_path: Path,
    file_prefix: Optional[str] = None,
    custom_filename: Optional[str] = None,
) -> str:
    """Saves an Agno Workflow step output to a file.

    Args:
        step_output: The StepOutput object to save
        output_path (Path): Output path for saved files
        file_prefix (str): Optional prefix for the filename
        custom_filename (str): Custom filename (overrides automatic naming)

    Returns:
        The filename that was saved
    """
    file_tools = FileTools(base_dir=Path(output_path))

    # Generate filename if not provided
    if custom_filename:
        filename = custom_filename
    else:
        step_name = getattr(step_output, "step_name", "unknown_step")
        safe_step_name = step_name.lower().replace(" ", "_").replace("-", "_")
        prefix = f"{file_prefix}_" if file_prefix else ""
        filename = f"{prefix}{safe_step_name}_output.json"

    # Convert content to JSON string
    if hasattr(step_output.content, "model_dump_json"):
        content = step_output.content.model_dump_json(indent=2)
    elif hasattr(step_output.content, "model_dump"):
        content = json.dumps(step_output.content.model_dump(), indent=2)
    else:
        content = json.dumps(step_output.content, indent=2, default=str)

    # Save the file
    file_tools.save_file(contents=content, file_name=filename)
