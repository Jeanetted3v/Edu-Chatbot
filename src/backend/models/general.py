from pydantic import Basemodel


class GeneralResponse(Basemodel):
    response: str