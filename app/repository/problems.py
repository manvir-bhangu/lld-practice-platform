from app.domain.default_rubric import DEFAULT_RUBRIC
from app.domain.errors import NotFound
from app.domain.problem import Problem


class ProblemCatalog:
    def __init__(self, problems: list[Problem]):
        self._problems = {p.id: p for p in problems}

    def list(self) -> list[Problem]:
        return list(self._problems.values())

    def get(self, problem_id: str) -> Problem:
        try:
            return self._problems[problem_id]
        except KeyError:
            raise NotFound(f"Unknown problem: {problem_id}") from None


def build_default_catalog() -> ProblemCatalog:
    return ProblemCatalog([
        Problem(
            id="parking-lot",
            title="Parking Lot",
            summary="Design a multi-level parking lot that parks vehicles, issues tickets and charges a fee on exit.",
            requirements=(
                "The lot has multiple levels, each with spots of different sizes (small, medium, large).",
                "Motorcycles, cars and buses are supported; a vehicle may only use a spot that fits it.",
                "Entering issues a ticket; leaving requires the ticket and frees the spot.",
                "The fee depends on parked duration, and the pricing rule must be easy to change (hourly, flat, etc.).",
                "Handle a full lot, and invalid or already-used tickets.",
            ),
            expected_entities=("ParkingLot", "Spot", "Vehicle", "Ticket"),
            rubric=DEFAULT_RUBRIC,
        ),
        Problem(
            id="elevator",
            title="Elevator System",
            summary="Design the control logic for a building with several elevators.",
            requirements=(
                "A building has multiple elevators serving multiple floors.",
                "Users request an elevator from a floor (up or down) and pick a destination inside the car.",
                "A scheduling strategy decides which elevator serves a request, and it must be swappable.",
                "Each elevator tracks its direction, current floor and pending stops, and respects a weight limit.",
                "Handle invalid floors, overload, and an elevator that is out of service.",
            ),
            expected_entities=("Elevator", "Floor", "Request", "Direction"),
            rubric=DEFAULT_RUBRIC,
        ),
        Problem(
            id="vending-machine",
            title="Vending Machine",
            summary="Design a vending machine that accepts payment, dispenses products and returns change.",
            requirements=(
                "The machine holds products in slots, each with a price and quantity.",
                "A user inserts money, selects a product, and receives the product and any change.",
                "Behaviour depends on machine state (idle, has money, dispensing, out of service).",
                "Handle insufficient funds, sold-out products, and being unable to return exact change.",
                "New payment methods should be addable without rewriting the core flow.",
            ),
            expected_entities=("VendingMachine", "Product", "Inventory", "Payment"),
            rubric=DEFAULT_RUBRIC,
        ),
    ])