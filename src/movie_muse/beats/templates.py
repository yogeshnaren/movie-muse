"""Original story-function templates. Licensed names are identifiers only.

Slot labels and guidance are original Movie Muse text. They do not copy
copyrighted beat-sheet prose from any third-party workbook.
"""

from __future__ import annotations

from movie_muse.beats.types import CatalogEntry, FrameworkKind

# (key, label, guidance) — original story functions, not third-party beat names.
THREE_ACT_SLOTS: tuple[tuple[str, str, str], ...] = (
    (
        "opening_movement",
        "Opening movement",
        "Establish circumstances, relationships, and the pressure that starts the story.",
    ),
    (
        "rising_movement",
        "Rising movement",
        "Complications accumulate and choices become harder to reverse.",
    ),
    (
        "closing_movement",
        "Closing movement",
        "The central conflict is faced and the new circumstances are shown.",
    ),
)

LICENSED_FIFTEEN_FUNCTION_SLOTS: tuple[tuple[str, str, str], ...] = (
    (
        "opening_condition",
        "Opening condition",
        "Show the starting world and the protagonist's place in it.",
    ),
    (
        "thematic_question",
        "Thematic question",
        "Pose the value conflict the story will test, without prescribing an answer.",
    ),
    (
        "world_establishment",
        "World establishment",
        "Introduce the people, rules, and stakes that make later turns legible.",
    ),
    (
        "inciting_pressure",
        "Inciting pressure",
        "An event forces the protagonist out of the opening condition.",
    ),
    (
        "resistance_to_change",
        "Resistance to change",
        "The protagonist hesitates, bargains, or looks for a way back.",
    ),
    (
        "commitment_to_pursuit",
        "Commitment to pursuit",
        "A choice commits the protagonist to the new problem.",
    ),
    (
        "parallel_thread",
        "Parallel thread",
        "A second relationship or plotline comments on the main pursuit.",
    ),
    (
        "promise_of_premise",
        "Promise of the premise",
        "Deliver the distinctive situations the story advertised.",
    ),
    (
        "turn_of_fortune",
        "Turn of fortune",
        "A midpoint shift raises cost or reveals a false victory.",
    ),
    (
        "tightening_opposition",
        "Tightening opposition",
        "Antagonistic forces close options and raise the cost of delay.",
    ),
    (
        "lowest_point",
        "Lowest point",
        "The pursuit appears to fail and the old plan is no longer viable.",
    ),
    (
        "quiet_reckoning",
        "Quiet reckoning",
        "The protagonist faces what the failure means before the last push.",
    ),
    (
        "turn_toward_climax",
        "Turn toward climax",
        "A new plan or insight aims the story at the final confrontation.",
    ),
    (
        "climactic_action",
        "Climactic action",
        "The protagonist acts on the new plan against the central opposition.",
    ),
    (
        "closing_condition",
        "Closing condition",
        "Show what has changed in the world and in the protagonist.",
    ),
)

LICENSED_TWELVE_FUNCTION_SLOTS: tuple[tuple[str, str, str], ...] = (
    (
        "ordinary_circumstances",
        "Ordinary circumstances",
        "The starting life the protagonist will leave, at least for a time.",
    ),
    (
        "invitation_to_change",
        "Invitation to change",
        "A disruption invites the protagonist into a larger conflict.",
    ),
    (
        "resistance",
        "Resistance",
        "Fear, duty, or disbelief keeps the protagonist from answering.",
    ),
    (
        "guidance_figure",
        "Guidance figure",
        "Someone or something supplies knowledge, tools, or courage.",
    ),
    (
        "commitment_crossing",
        "Commitment crossing",
        "The protagonist leaves the ordinary circumstances in earnest.",
    ),
    (
        "trials_and_alliances",
        "Trials and alliances",
        "Tests reveal allies, rivals, and the rules of the new arena.",
    ),
    (
        "approach_to_ordeal",
        "Approach to ordeal",
        "The protagonist prepares to face the story's central danger.",
    ),
    (
        "central_ordeal",
        "Central ordeal",
        "A decisive confrontation that the protagonist may not survive unchanged.",
    ),
    (
        "reward_after_ordeal",
        "Reward after ordeal",
        "Something of value is gained, though it may be incomplete.",
    ),
    (
        "return_pressure",
        "Return pressure",
        "The conflict pursues the protagonist back toward home or consequence.",
    ),
    (
        "final_test",
        "Final test",
        "The last proving of what the protagonist learned in the ordeal.",
    ),
    (
        "return_with_change",
        "Return with change",
        "The protagonist brings a changed capacity back to ordinary life.",
    ),
)

KIND_SLOTS: dict[FrameworkKind, tuple[tuple[str, str, str], ...]] = {
    FrameworkKind.THREE_ACT: THREE_ACT_SLOTS,
    FrameworkKind.SAVE_THE_CAT: LICENSED_FIFTEEN_FUNCTION_SLOTS,
    FrameworkKind.HEROS_JOURNEY: LICENSED_TWELVE_FUNCTION_SLOTS,
}

CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        kind=FrameworkKind.THREE_ACT,
        title="Three-movement structure",
        rights_required=False,
        slot_count=len(THREE_ACT_SLOTS),
        notes="Permitted original labels. Guidance only; not a scoring formula.",
    ),
    CatalogEntry(
        kind=FrameworkKind.SAVE_THE_CAT,
        title="Named fifteen-function licensed template",
        rights_required=True,
        slot_count=len(LICENSED_FIFTEEN_FUNCTION_SLOTS),
        notes=(
            "Requires a licensed or permitted rights source. Story-function keys "
            "are original; this package does not embed third-party workbook text."
        ),
    ),
    CatalogEntry(
        kind=FrameworkKind.HEROS_JOURNEY,
        title="Named twelve-function licensed template",
        rights_required=True,
        slot_count=len(LICENSED_TWELVE_FUNCTION_SLOTS),
        notes=(
            "Requires a licensed or permitted rights source. Story-function keys "
            "are original; this package does not embed third-party workbook text."
        ),
    ),
    CatalogEntry(
        kind=FrameworkKind.CUSTOM,
        title="Custom framework",
        rights_required=False,
        slot_count=0,
        notes="Author-defined original slots. Guidance only.",
    ),
)
