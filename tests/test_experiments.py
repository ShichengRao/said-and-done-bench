"""The experiments' own logic: chat-framing prompts and scoring, and the kickoff note."""

import importlib.util
from pathlib import Path

from beambench import prompts

spec = importlib.util.spec_from_file_location('chat_framing', Path(__file__).resolve().parent.parent / 'experiments' / 'chat_framing.py')
chat_framing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat_framing)


def test_options_are_shuffled_per_sample_and_scored_by_letter():
  scenario = chat_framing.SCENARIOS[0]
  orders = {tuple(chat_framing.build(scenario, sample)[1].values()) for sample in range(10)}
  assert len(orders) > 1  # Not always the same order.
  prompt, mapping = chat_framing.build(scenario, 3)
  letter = next(letter for letter, option in mapping.items() if option == 'rules_blocked')
  assert f'{letter}. Keep the implementation that follows the rules' in prompt
  assert chat_framing.parse(f'Sure. {{"choice": "{letter.lower()}", "why": "Rule 6."}}', mapping) == ('rules_blocked', 'Rule 6.')
  assert chat_framing.parse('no json here', mapping) == (None, None)


def test_every_scenario_names_its_honest_option_and_beams_agent_choice():
  for scenario in chat_framing.SCENARIOS:
    assert scenario['honest'] in scenario['options'] and scenario['agent_choice'] in scenario['options']
    assert scenario['honest'] != scenario['agent_choice']


def test_an_experiment_can_add_a_note_to_the_kickoff():
  text = prompts.kickoff('Fix it.', note='Blocked is a fine answer.')
  assert text.endswith('\n\nBlocked is a fine answer.') and prompts.kickoff('Fix it.').endswith('for details.')
