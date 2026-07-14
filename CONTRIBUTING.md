# Contributing

Thank you for helping to improve the Thunderdome project. Small contributions are welcome, and you do not need access to the dome or specialist hardware to take part.

Useful contributions include:

- Correcting spelling, grammar or broken links
- Making an explanation easier to understand
- Adding photographs, diagrams or build notes
- Suggesting lighting effects, games or interactive features
- Improving or testing the software
- Sharing relevant experience with LEDs, WLED or geodesic domes

## Before you start

For a small correction, feel free to open a pull request directly. For a larger change or an idea that needs discussion, [open an issue](https://github.com/dogsbodytech/thunderdome/issues/new/choose) first.

Please do not publish passwords, API keys, private credentials or other secrets. Only contribute photographs and other media that you have permission to share.

## Making a contribution

1. Fork the repository on GitHub.
2. Create a branch with a short, descriptive name.
3. Make one focused change.
4. Check your work and any links you have added.
5. Open a pull request explaining what you changed and why.

If you are new to GitHub, corrections made with GitHub's web-based file editor are absolutely fine.

## Documentation style

- Use British English.
- Keep explanations friendly and understandable without specialist knowledge.
- Leave a space between a number and its unit, for example `12 V`, `30 mm` and `100 W`.
- Use commas in numbers of 1,000 or more.
- Use descriptive link text rather than pasting a URL as the link text.
- Link to the canonical supplier page and remove shopping-cart or tracking parameters.
- Add useful alternative text to images and diagrams.

## Checking changes

Documentation changes should be previewed on GitHub and checked for broken links.

For changes to the current Python pulse generator, run:

```bash
python3 -m py_compile software/dome-audio-reactor/pulse_generator.py
```

For hardware changes, describe how you checked the recommendation and clearly identify anything that has not been tested on the physical dome.

## Pull requests

Please keep pull requests focused. A useful description includes:

- What changed
- Why the change is useful
- How it was checked or tested
- Any remaining uncertainty

By participating in this project, you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).
