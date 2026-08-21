from src.autonomy_router import AutonomyRouter


def test_autonomy_router_levels():
    router = AutonomyRouter()
    assert router.route(0.2).level == "autonomous"
    assert router.route(0.5).level == "confirm"
    assert router.route(0.9).level == "review"
