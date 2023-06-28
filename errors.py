class ServerStopped(Exception):
    """
    Raised when the Bedrock Server has stopped
    """
    def __init__(self):
        super().__init__()


class ServerCrash(ServerStopped):
    """
    Raised when the Bedrock Server has Crashed
    """
    def __init__(self):
        super().__init__()


class UserRequestedStop(ServerStopped):
    """
    Raised when the user requests the Bedrock Server to stop
    """
    def __init__(self):
        super().__init__()


class ServerRestart(Exception):
    """
    Raised when NexusCore orders a server restart
    """
    def __init__(self):
        super().__init__()