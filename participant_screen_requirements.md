# Participant Screen Requirements

Use this wording in the crowd-sourcing task description or consent/instruction
page.

```text
Please complete this study on a laptop or desktop computer, not on a phone or
tablet.

Recommended setup:
- 13-inch or larger laptop/desktop screen
- Screen resolution of at least 1366 x 768
- Browser zoom set to 100%
- Browser window maximized or full screen
- Stable internet connection

The study shows two videos side by side. A small screen, mobile device, browser
zoom above 100%, or a non-maximized browser window may make the comparison
difficult and may affect the reliability of the response.
```

Implementation note:

```text
The Streamlit app video area is tuned for a standard laptop viewport. Each trial
uses a two-column 16:9 side-by-side layout, with object-fit: contain so the full
video is visible without cropping.
```
