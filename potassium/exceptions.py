class InvalidEndpointTypeException(Exception):
    def __init__(self):
        super().__init__("Invalid endpoint type. Must be 'handler' or 'background'")


class RouteAlreadyInUseException(Exception):
    def __init__(self):
        super().__init__("Route already in use")


