"""Portable provider schemas; richer validation remains local."""

from copy import deepcopy


def export_tools(tools):
    exported = deepcopy(tools)
    for tool in exported:
        schema = tool['input_schema']
        if schema.get('type') != 'object':
            raise ValueError('Tool inputs must be objects: ' + tool['name'])
        # Anthropic rejects root composition, including through OpenRouter.
        # Keep these requirements in the original local validation schema.
        if 'oneOf' in schema or 'allOf' in schema:
            raise ValueError('Unsupported local schema composition: ' + tool['name'])
        schema.pop('anyOf', None)
        if not set(schema.get('required', [])) <= set(schema.get('properties', {})):
            raise ValueError('Unknown required field: ' + tool['name'])
    return exported
