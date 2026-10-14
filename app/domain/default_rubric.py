from app.domain.problem import Criterion, Rubric

DEFAULT_RUBRIC = Rubric(
    criteria=(
        Criterion("completeness", "Completeness",
                  "All required design sections are filled in"),
        Criterion("entity_coverage", "Entity coverage",
                  "Core entities for this problem are identified"),
        Criterion("responsibilities", "Class responsibilities",
                  "Each class has one clear responsibility"),
        Criterion("coupling_cohesion", "Coupling and cohesion",
                  "Classes depend on abstractions, related behaviour lives together"),
        Criterion("extensibility", "Extensibility",
                  "The design absorbs likely new requirements without rewrites"),
        Criterion("edge_cases_tradeoffs", "Edge cases and trade-offs",
                  "Failure cases and design trade-offs are discussed"),
    )
)