#!/usr/bin/env python3
"""The 8 October 2026 press conference, moment by moment, declared once.

WHY THIS PAGE. The administration made a series of specific, checkable
claims about H-1B, PERM and J-1 use. This site holds the federal data behind
most of them. A page that puts the claim and the data side by side is more
useful than either alone, and it is the one thing here a reader can audit
sentence by sentence against a recording.

THE RULES THIS PAGE FOLLOWS, and they matter more here than anywhere else:

  * QUOTE EXACTLY. Every quotation is lifted from the published captions,
    with its timestamp, so a reader can jump to it and hear it said.
  * SAY WHO SAID IT. Six people spoke. Attributing one person's words to
    another would be the worst error this page could make.
  * OUR FIGURES COME FROM OUR DATA. Every number on the right-hand side
    resolves from a built dataset at render time.
  * WHERE WE AGREE, SAY SO. WHERE WE DIFFER, SAY THAT TOO. The 61% figure
    checks out. The 38% national average does not match the survey we hold.
    A page that reported only the half that suited the argument would not be
    worth publishing.
  * NO LEGAL CLAIM. An investigation was announced. That is a fact with a
    date. Nothing here says any institution or firm broke a law.
"""
from __future__ import annotations

from dataclasses import dataclass, field

VIDEO_ID = "7QAu9FOEOv8"
SOURCE_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
TITLE = "Vice President JD Vance Holds Press Conference on Fighting Visa Fraud"
PUBLISHER = "The White House"
DATE = "8 October 2026"


@dataclass(frozen=True)
class Moment:
    t: int                      # seconds into the recording
    who: str
    quote: str                  # verbatim, from the published captions
    heading: str
    #: What this site can say about it. Each entry is
    #: (prose, dataset stem, dotted path, format) and the figure is resolved
    #: at build time; a path that does not resolve fails the build.
    evidence: tuple = field(default_factory=tuple)
    note: str = ""              # context or a limit, in the site's voice
    links: tuple = field(default_factory=tuple)
    verdict: str = ""           # "confirms" | "differs" | "" (no check)


MOMENTS: tuple[Moment, ...] = (
    Moment(
        t=26, who="Vice President JD Vance",
        quote="This is a great day for American workers because we are "
              "taking some very concrete actions to cut down on some of the "
              "H-1B and J1 visa fraud that we've been tracking over the past "
              "several months.",
        heading="What was announced",
        note="Three things followed: PERM suspensions for eight named "
             "companies, a J-1 investigation into nine named universities, "
             "and a visa-fraud strike team. The rest of this page takes the "
             "claims in the order they were made.",
    ),
    Moment(
        t=104, who="Vice President JD Vance",
        quote="They will say, maybe they'll put an advertisement in a small "
              "town newspaper... and they will use that lack of a response "
              "to then go and replace American workers.",
        heading="The recruitment test",
        note="This describes the PERM labour-market test: before sponsoring "
             "a worker for permanent residence an employer must advertise "
             "the role and show no qualified American applied. The "
             "disclosure files record that a test happened. They do not "
             "record the advertisement, the applicants, or why they were "
             "rejected, so the claim cannot be checked from published data. "
             "That gap is an ask on this site.",
        links=(("/data_requests", "What the record does not hold"),),
    ),
    Moment(
        t=117, who="Vice President JD Vance",
        quote="When somebody comes in on an H-1B, they are completely "
              "subordinate to that company. If they lose that job, they have "
              "to leave the country.",
        heading="Why the tie to one employer matters",
        note="Status depends on the job, which is a fact of the visa rather "
             "than a finding in the data. What the data does show is the "
             "price attached: an employer owes no Social Security or "
             "Medicare tax on a student working under practical training, "
             "and neither does the worker.",
        evidence=(("forgone per $100,000 of payroll, employer and employee "
                   "side together", "fica_exposure",
                   "per_100k_payroll.employer_plus_employee", "usd"),),
        links=(("/visa-schools#cheaper", "Why an OPT hire costs less"),),
    ),
    Moment(
        t=141, who="Vice President JD Vance",
        quote="The H-1B visa is how the people get into the United States in "
              "the first place, and then a PERM program is how those "
              "employees stay.",
        heading="PERM is the step this site can see",
        verdict="confirms",
        note="PERM is the only federal disclosure file that records a "
             "worker's citizenship, which is why this site can say who "
             "public employers sponsor and the H-1B files cannot. The series "
             "ends with FY2024: the Department of Labor removed every worker "
             "field from the FY2025 file, 155 columns down to 137.",
        evidence=(("certified public-employer filings, FY2013–FY2024",
                   "public_employer_perm", "public_rows", "n"),),
        links=(("/public-sector-visas", "Who the public sector sponsors"),
               ("/data_requests", "The ask to restore those fields")),
    ),
    Moment(
        t=182, who="Vice President JD Vance",
        quote="Microsoft laid off last year 6,000 American workers. At the "
              "same time, the company benefited from 6,300 H1B visas and "
              "almost 3,000 green cards.",
        heading="The Microsoft figures",
        note="This site does not hold layoff counts, so the comparison "
             "cannot be reproduced here. It does hold what Microsoft filed. "
             "Note that H-1B approvals must never be added across initial "
             "and continuing: a continuing approval is the same person "
             "renewed, so summing them counts one worker once a year for as "
             "long as they stay.",
        links=(("/query", "Check the filings yourself"),),
    ),
    Moment(
        t=322, who="Vice President JD Vance",
        quote="These firms that help corporations apply and find H-1B visa "
              "candidates. They're commonly called the witches, the four "
              "major outsourcing firms.",
        heading="The staffing firms",
        verdict="confirms",
        note="This site identifies these firms from the disclosure files "
             "rather than from a list. Joining employers to their industry "
             "puts Infosys, Tata Consultancy, Cognizant, Wipro, HCL and "
             "Capgemini at the top of filing volume — the same firms "
             "suspended from PERM later in this press conference.",
        evidence=(("employers that meet this site\u2019s staffing-firm test",
                   "visa_bodyshops", "body_shop_totals.employers", "n"),
                  ("certified filings they account for",
                   "visa_bodyshops", "body_shop_totals.filings", "n"),),
        links=(("/bodyshops", "The firms that meet the test"),
               ("/query", "Run the join")),
    ),
    Moment(
        t=348, who="Vice President JD Vance",
        quote="If you are working as an H-1B visa in the United States of "
              "America, you're earning $20,000 less than an American citizen "
              "hired in the same position. If you were brought in by one of "
              "these foreign outsourcing firms, you're making $48,000 less.",
        heading="The wage gap",
        note="Every wage this site holds is an OFFERED wage, because that is "
             "the only wage published. What a worker is actually paid "
             "appears on a W-2, which Treasury holds and the Department of "
             "Labor does not. So a gap of this kind cannot be confirmed or "
             "refuted from the public record, and asking for the matched "
             "tabulation is an ask on this site.",
        links=(("/data_requests", "Wages actually paid, not offered"),),
    ),
    Moment(
        t=411, who="Vice President JD Vance",
        quote="There are nine universities in particular that we believe "
              "merit an investigation. Those universities are Harvard, Yale, "
              "Stanford, Brown, the University of Pittsburgh, UC Davis, "
              "Caltech, Arizona State, and MIT.",
        heading="The nine universities",
        note="An investigation was announced on this date. This page reports "
             "that it was announced and what the federal survey counts. It "
             "makes no claim that any of these institutions broke a law.",
        links=(("/postdocs#the-nine", "All nine, with their postdoc counts"),),
    ),
    Moment(
        t=434, who="Vice President JD Vance",
        quote="These universities are employing J1 visas for federally "
              "funded grants at a rate of about 61%. The national average is "
              "38%.",
        heading="The 61% checks out. The 38% does not match this survey.",
        verdict="differs",
        note="Computed from the NSF Survey of Graduate Students and "
             "Postdoctorates, the nine named universities come to the figure "
             "given. The national average on the same measure is not 38%. "
             "That difference decides what the story is: if the nine sat far "
             "above a low national average they would be outliers, and an "
             "enforcement action against nine institutions would address it. "
             "They do not. The American postdoctoral workforce is a minority "
             "of itself almost everywhere, and the nine look much like the "
             "rest of the country. That is the larger finding, and it is "
             "closer to the argument being made than the figure quoted.",
        evidence=(("the nine named universities, share of postdocs holding a "
                   "temporary visa", "postdoc_citizenship",
                   "named_institutions.share", "pct1"),
                  ("every institution in the survey",
                   "postdoc_citizenship", "national.share", "pct1"),
                  ("postdoctoral appointees counted",
                   "postdoc_citizenship", "national.postdocs", "n"),
                  ("of those posts are federally supported",
                   "postdoc_citizenship", "national.federally_supported_share",
                   "pct1")),
        links=(("/postdocs", "Who holds the postdoc jobs"),),
    ),
    Moment(
        t=656, who="Labor Secretary Keith Sonderling",
        quote="I am hereby suspending from the permanent labor certification "
              "program some of the largest IT outsourcing firms in the "
              "world. Cognizant, Infosys, Tata, Whipro, HCL, and Capgeemini. "
              "And also due to multiple active federal investigations, the "
              "Department of Labor suspending Microsoft and Adobe from the "
              "program.",
        heading="Eight companies suspended from PERM",
        note="PERM is the mechanism described earlier as how an H-1B holder "
             "stays permanently. Suspension stops new and pending "
             "applications from these employers. It does not affect anyone "
             "already holding permanent residence.",
        links=(("/bodyshops", "What the filings show about these firms"),),
    ),
    Moment(
        t=757, who="Attorney General Todd Blanch",
        quote="This announcement today should send and does send a strong "
              "signal to every single employer in the United States that the "
              "Trump administration will not tolerate discrimination against "
              "American workers.",
        heading="The enforcement frame",
        note="No published federal source records graduate applications or "
             "admissions by citizenship, so whether American applicants are "
             "declining, being declined, or not applying cannot be "
             "determined from the data. This site asks for that collection.",
        links=(("/data_requests", "Graduate admissions by citizenship"),),
    ),
    Moment(
        t=998, who="Deputy Chief of Staff Stephen Miller",
        quote="He had at his rallies American workers in good paying middle "
              "class jobs with pensions who were laid off and forced to "
              "train their foreign replacements as the condition of their "
              "severance.",
        heading="Training your replacement",
        note="Not a measurable claim in the disclosure files, which record "
             "filings rather than what happened in an office. Included here "
             "because it was said, and because a reader comparing the "
             "recording with this page should find every substantive passage "
             "accounted for.",
    ),
    Moment(
        t=1265, who="Labor Inspector General Anthony Desposito",
        quote="Subpoenas have been served, investigations are underway, and "
              "nobody will be getting a free pass because their name is "
              "carved into an expensive building.",
        heading="The investigation is live",
        note="Reported as a fact with a date. The outcome is unknown and "
             "this page draws no conclusion from the existence of an "
             "investigation.",
    ),
    Moment(
        t=1316, who="Labor Inspector General Anthony Desposito",
        quote="The Chinese Communist Party doesn't need to kick down the "
              "doors of America's research laboratories if our own "
              "institutions are willing to leave the doors wide open.",
        heading="The research-security argument",
        note="This site measures who is in the laboratories, not what leaves "
             "them. A citizenship share is not evidence of anything "
             "improper by any individual, and nothing here should be read "
             "that way. What it does show is the scale: in several strategic "
             "fields the graduate pipeline is overwhelmingly non-resident.",
        evidence=(("non-resident share of petroleum engineering doctorates",
                   "critical_industries",
                   "industries[slug=petroleum].levels[level=Doctorate].share",
                   "pct1"),),
        links=(("/industries/petroleum", "Petroleum engineering"),
               ("/postdocs#federal", "Who pays for the posts")),
    ),
    Moment(
        t=1544, who="FTC Chairman Andrew Ferguson",
        quote="America is not a jobs program for the rest of the world. We "
              "didn't build our institutions for the rest of the world. We "
              "built them for Americans.",
        heading="The thesis, stated from the podium",
        note="This is the argument this site was built to test with federal "
             "data. The measured finding sits on one page and the argument "
             "on another, deliberately, because a reader may reject the "
             "argument and accept every figure in it.",
        evidence=(("doctoral and master\u2019s theses from 106 American universities",
                   "name_lists", "total_records", "n"),
                  ("postdoctoral appointees who are American citizens or permanent residents",
                   "postdoc_citizenship", "national.us", "n"),),
        links=(("/overview", "The measured finding"),
               ("/name-lists", "The dissertations themselves")),
    ),
    Moment(
        t=1774, who="Vice President JD Vance",
        quote="Never believe the lie that Americans are not good enough to "
              "build a future for Americans.",
        heading="The close",
        note="",
    ),
    Moment(
        t=2529, who="Vice President JD Vance",
        quote="The nature of the fraud is fundamentally that when you apply "
              "for these visa programs, you make a couple of certifications. "
              "One of those certifications is that the person that you're "
              "bringing in has a hyper specialized, hyper capable skill set. "
              "And that's clearly not the case if you're just replacing one "
              "American worker with a foreign indentured servant.",
        heading="Asked directly: what is the fraud?",
        note="A reporter asked whether this was illegal conduct or a legal "
             "pathway the administration objects to. The answer rests on the "
             "specialty-occupation certification. This site can show what "
             "occupations and wages were certified; it cannot show intent, "
             "and it makes no claim about any employer's state of mind.",
        evidence=(("certified H-1B applications in the disclosure files",
                   "h1b_by_industry", "certified_filings", "n"),),
        links=(("/industries", "What was certified, by industry"),
               ("/query", "The occupation and wage tables")),
    ),
)
