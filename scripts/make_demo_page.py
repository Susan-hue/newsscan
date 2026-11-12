"""Draw a synthetic two-column "newspaper" page, so you can try the app before you have a real scan.

Usage: python scripts/make_demo_page.py demo.png

This is an EASY case (clean text, straight lines, a wide gutter between the columns). Do not read
anything into how well it scans: real newspaper photos are much harder. See docs/decisions/ADR-003.
"""

import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1]
width, height = 1700, 2200
page = Image.new("RGB", (width, height), (245, 243, 236))  # off-white newsprint
draw = ImageDraw.Draw(page)

headline = ImageFont.load_default(size=84)
body = ImageFont.load_default(size=34)

draw.text((90, 80), "COUNCIL APPROVES TRANSIT BUDGET", fill=(20, 20, 20), font=headline)
draw.line((90, 200, width - 90, 200), fill=(20, 20, 20), width=4)

column_one = (
    "The city council voted on Tuesday to approve a new transit budget that adds three bus "
    "routes and extends evening service across the northern districts. Officials said the "
    "plan was developed after a year of public consultation with residents and local "
    "businesses. Construction is expected to begin next spring, pending approval from the "
    "provincial government."
)
column_two = (
    "Critics argued that the budget does not go far enough. A spokesperson for the "
    "riders association said wait times on the east side remain too long and that fares "
    "should be frozen for another year. The mayor responded that the council will review "
    "the figures again in the autumn."
)

for x, text in ((90, column_one), (900, column_two)):
    y = 240
    for line in textwrap.wrap(text, width=38):
        draw.text((x, y), line, fill=(25, 25, 25), font=body)
        y += 50

page.save(out)
print("wrote", out)
