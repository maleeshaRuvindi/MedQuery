class GuardrailError(Exception):
    def __init__(self, message: str, layer: str, rule: str):
        self.message = message
        self.layer = layer    # "input", "sql", "output"
        self.rule = rule      # "injection", "select_only", "pii", etc.
        super().__init__(message)