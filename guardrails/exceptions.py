class GuardrailError(Exception):
    def __init__(self, message: str, layer: str, rule: str):
        self.message = message
        self.layer = layer    
        self.rule = rule      
        super().__init__(message)