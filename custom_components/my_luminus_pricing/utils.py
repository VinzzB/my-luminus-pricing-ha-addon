import re

def camel_to_snake_case(text: str) -> str:
    """Zet CamelCase om naar snake_case."""
    # Voegt een underscore toe voor elke hoofdletter die volgt op een kleine letter
    str1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    # Behandelt opeenvolgende hoofdletters (zoals HTTPResponse -> http_response)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', str1).lower()  