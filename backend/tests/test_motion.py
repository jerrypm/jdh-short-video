import json
from pathlib import Path
import subprocess
import pytest
from backend.motion import (
    Motion,
    VisualMotion,
    TextMotion,
    evaluate_visual,
    evaluate_text,
    frame_range,
)
from backend.models import Project, Scene
from backend import captions

ROOT = Path(__file__).resolve().parents[2]


def test_old_projects_gain_none_without_changing_timeline():
    project = Project(
        id="a" * 32,
        name="Legacy",
        scenes=[Scene(id="one", duration=99, audio_id="b" * 32, audio_in=3)],
    )
    assert project.scenes[0].motion.visual.preset == "none"
    assert project.scenes[0].motion.caption.preset == "none"
    assert project.scenes[0].motion.callout is None
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored.scenes[0].duration == 99 and restored.scenes[0].audio_in == 3


@pytest.mark.parametrize(
    "value",
    [
        {"version": 2},
        {"version": True},
        {"filter": "movie=/tmp/private"},
        {"visual": {"preset": "crossfade"}},
        {"visual": {"preset": "zoompan=z=10"}},
        {"visual": {"amount": 0.121}},
        {"visual": {"amount": float("nan")}},
        {"visual": {"focus_x": -1}},
        {"visual": {"focus_y": 1.1}},
        {"visual": {"start_frame": 1.5}},
        {"visual": {"start_frame": True}},
        {"visual": {"start_frame": 8, "end_frame": 8}},
        {"caption": {"easing": "eval(code)"}},
        {"callout": {"text": "Hello", "x": 800, "width": 400}},
        {"callout": {"text": "Hello", "target_y": 1700}},
        {"callout": {"text": "Hello", "path": "/tmp/private"}},
        {"callout": {"text": "Hello", "y": 1450, "entrance": {"preset": "slide_up"}}},
        {
            "callout": {
                "text": "Hello",
                "target_y": 1600,
                "entrance": {"preset": "slide_up"},
            }
        },
    ],
)
def test_untrusted_parameters_never_become_expressions(value):
    with pytest.raises(ValueError):
        Motion.model_validate(value)


def test_frame_boundaries_short_scene_clipping_and_none():
    visual = VisualMotion(
        preset="zoom_in",
        amount=0.1,
        focus_x=1.0,
        focus_y=0.0,
        start_frame=2,
        end_frame=6,
        easing="linear",
    )
    assert evaluate_visual(visual, 1, 9) == {"scale": 1, "x": 0, "y": 0}
    assert evaluate_visual(visual, 4, 9)["scale"] == pytest.approx(1.05)
    assert evaluate_visual(visual, 6, 9)["x"] == pytest.approx(-108)
    assert evaluate_visual(visual, 8, 9) == evaluate_visual(visual, 6, 9)
    assert evaluate_visual(visual, 6, 9, False) == {"scale": 1, "x": 0, "y": 0}
    assert frame_range(VisualMotion(start_frame=60, end_frame=100), 9) == (7, 8)
    text = TextMotion(preset="slide_up", start_frame=2, end_frame=6)
    assert evaluate_text(text, 1, 9) == {"opacity": 0, "y": 48}
    assert evaluate_text(text, 4, 9) == {"opacity": 0.5, "y": 24}
    assert evaluate_text(text, 6, 9) == {"opacity": 1, "y": 0}
    assert evaluate_text(text, 0, 9, False) == {"opacity": 1, "y": 0}


def test_actual_react_evaluator_matches_python_at_all_keyframes():
    cases = []
    for preset in [
        "none",
        "zoom_in",
        "zoom_out",
        "pan_left",
        "pan_right",
        "pan_up",
        "pan_down",
    ]:
        for easing in ["linear", "smoothstep"]:
            for frame in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
                motion = Motion(
                    visual=VisualMotion(
                        preset=preset,
                        amount=0.12,
                        focus_x=0.2,
                        focus_y=0.8,
                        start_frame=2,
                        end_frame=6,
                        easing=easing,
                    ),
                    caption=TextMotion(preset="fade", start_frame=2, end_frame=6),
                )
                cases.append(
                    {
                        "motion": motion.model_dump(),
                        "frame": frame,
                        "duration": 9,
                        "enabled": True,
                    }
                )
    result = subprocess.run(
        ["node", "--import", "tsx", "../script/motion_reference.ts"],
        input=json.dumps(cases),
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT / "web",
    )
    for case, actual in zip(cases, json.loads(result.stdout), strict=True):
        motion = Motion.model_validate(case["motion"])
        assert actual["visual"] == pytest.approx(
            evaluate_visual(motion.visual, case["frame"], 9)
        )
        assert actual["caption"] == pytest.approx(
            evaluate_text(motion.caption, case["frame"], 9)
        )


def test_callout_is_bounded_literal_text_and_does_not_change_srt(tmp_path):
    from backend.motion import Callout
    from PIL import Image

    label = Callout(text="Focus here")
    path = tmp_path / "callout.png"
    captions.callout_image(label, path)
    image = Image.open(path)
    assert image.size == (1080, 1920)
    left, top, right, bottom = image.getbbox()
    assert left >= 60 and top >= 130 and right <= 1022 and bottom <= 1619
    with pytest.raises(ValueError, match="Callout terlalu panjang"):
        captions.callout_image(Callout(text="word " * 24, width=160), path)
    captions.callout_image(
        Callout(
            text="Bottom edge\nTwo lines",
            y=1400,
            size=48,
            target_y=1564,
            entrance=TextMotion(preset="slide_up"),
        ),
        path,
    )
    # Pointer radius can extend six pixels beyond its target, as at rest.
    assert Image.open(path).getbbox()[3] + 48 <= 1619
    project = Project(
        id="a" * 32,
        name="QA",
        scenes=[Scene(id="one", caption="Keep these words", duration=90)],
    )
    before = captions.srt(project)
    project.scenes[0].motion = Motion(
        callout=label, caption=TextMotion(preset="slide_up")
    )
    assert captions.srt(project) == before
