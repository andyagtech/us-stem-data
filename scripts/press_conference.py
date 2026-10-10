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
    note: str = ""
    #: Points rendered as a list under the note. For a passage that
    #: announces several things at once, prose buries the count.
    bullets: tuple[str, ...] = ()
    #: (text, anchor) -- the specific federal request this passage
    #: turns on. Rendered in the site's accent and linked straight to
    #: that request, because "this site asks for it" is the action the
    #: page exists to prompt and it should not read as an aside.
    ask: tuple[str, str] | None = None
    links: tuple = field(default_factory=tuple)


MOMENTS: tuple[Moment, ...] = (
    Moment(
        t=26, who="Vice President JD Vance",
        quote="This is a great day for American workers because we are "
              "taking some very concrete actions to cut down on some of the "
              "H-1B and J1 visa fraud that we've been tracking over the past "
              "several months.",
        heading="What was announced",
        note="Three things followed.",
        bullets=("PERM suspensions for eight named companies.",
                 "A J-1 investigation into nine named universities.",
                 "A visa-fraud strike team."),
    ),
    Moment(
        t=104, who="Vice President JD Vance",
        quote="They will say, maybe they'll put an advertisement in a small "
              "town newspaper... and they will use that lack of a response "
              "to then go and replace American workers.",
        heading="The recruitment test",
        note="This is the PERM labour-market test: before sponsoring a "
             "worker for permanent residence an employer must advertise the "
             "role and show that no qualified American applied. The "
             "disclosure files record that a test took place. They do not "
             "record the advertisement, how many Americans applied, or why "
             "any were rejected. The Department of Labor holds that detail "
             "on the ETA-9089 and does not publish it.",
        ask=("Publish the recruitment detail from the ETA-9089: the "
             "advertisement, the number of American applicants, and the "
             "reason each was rejected. The employer already answers these "
             "questions on the form. Releasing them would settle this "
             "passage outright.",
             "/data_requests#ask-9"),
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
        note="Layoff counts are not a federal disclosure, so that half of "
             "the comparison comes from company reporting rather than from "
             "this site. What is public is everything Microsoft filed, by "
             "year, occupation and wage level, and it can be read here "
             "directly. One caution when citing approval totals: initial and "
             "continuing approvals must never be summed, because a "
             "continuing approval is the same worker renewed and adding them "
             "counts one person once a year for as long as they stay.",
        links=(("/query?sql=--%20Everything%20Microsoft%20filed%2C%20from%20the%20DOL%20disclosure%20files.%0A--%20Filings%2C%20not%20people%3A%20a%20certified%20application%20is%20permission%20to%0A--%20employ%2C%20never%20proof%20of%20a%20hire%2C%20and%20never%20a%20count%20of%20workers.%0ASELECT%20employer%2C%0A%20%20%20%20%20%20%20employer_filings%2C%0A%20%20%20%20%20%20%20median_wage%2C%0A%20%20%20%20%20%20%20low_level_pct%20AS%20pct_at_the_two_lowest_wage_levels%0AFROM%20h1b_employers%0AWHERE%20upper%28employer%29%20LIKE%20%27%25MICROSOFT%25%27%0AORDER%20BY%20employer_filings%20DESC", "Check the filings yourself"),),
    ),
    Moment(
        t=322, who="Vice President JD Vance",
        quote="These firms that help corporations apply and find H-1B visa "
              "candidates. They're commonly called the witches, the four "
              "major outsourcing firms.",
        heading="The staffing firms",
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
               ("/query?sql=--%20The%20staffing%20firms%20named%20in%20the%20press%20conference%2C%20joined%20to%20the%0A--%20industry%20they%20file%20under.%20Counted%20by%20APPLICATION%2C%20never%20by%0A--%20position%3A%20one%20application%20can%20cover%20forty%20workers%2C%20and%20weighting%0A--%20by%20positions%20hands%20every%20share%20to%20the%20bulk%20filers.%0ASELECT%20e.employer%2C%0A%20%20%20%20%20%20%20e.employer_filings%2C%0A%20%20%20%20%20%20%20e.median_wage%2C%0A%20%20%20%20%20%20%20e.low_level_pct%20AS%20pct_at_the_two_lowest_wage_levels%2C%0A%20%20%20%20%20%20%20i.naics%2C%0A%20%20%20%20%20%20%20i.top_title%0AFROM%20h1b_employers%20e%0ALEFT%20JOIN%20h1b_industry%20i%20ON%20e.naics%20%3D%20i.naics%0AWHERE%20upper%28e.employer%29%20LIKE%20%27%25INFOSYS%25%27%0A%20%20%20OR%20upper%28e.employer%29%20LIKE%20%27%25TATA%20CONSULTANCY%25%27%0A%20%20%20OR%20upper%28e.employer%29%20LIKE%20%27%25COGNIZANT%25%27%0A%20%20%20OR%20upper%28e.employer%29%20LIKE%20%27%25WIPRO%25%27%0A%20%20%20OR%20upper%28e.employer%29%20LIKE%20%27%25HCL%20%25%27%0A%20%20%20OR%20upper%28e.employer%29%20LIKE%20%27%25CAPGEMINI%25%27%0AORDER%20BY%20e.employer_filings%20DESC", "Run the join")),
    ),
    Moment(
        t=348, who="Vice President JD Vance",
        quote="If you are working as an H-1B visa in the United States of "
              "America, you're earning $20,000 less than an American citizen "
              "hired in the same position. If you were brought in by one of "
              "these foreign outsourcing firms, you're making $48,000 less.",
        heading="The wage gap",
        note="The disclosure files publish the wage an employer OFFERS, not "
             "the wage paid, so the offered figures understate any gap "
             "rather than overstate it. What this site can show at scale is "
             "where the offers sit: the staffing firms named a moment later "
             "file overwhelmingly at the lowest statutory wage levels. The "
             "figure that would settle the question outright is a Treasury "
             "tabulation of W-2 wages against the prevailing wage for the "
             "same occupation and area. Treasury holds it. Nobody has "
             "published it.",
        links=(("/data_requests", "Wages actually paid, not offered"),),
    ),
    Moment(
        t=411, who="Vice President JD Vance",
        quote="There are nine universities in particular that we believe "
              "merit an investigation. Those universities are Harvard, Yale, "
              "Stanford, Brown, the University of Pittsburgh, UC Davis, "
              "Caltech, Arizona State, and MIT.",
        heading="The nine universities",
        evidence=(("postdoctoral appointees across the nine",
                   "postdoc_citizenship", "named_institutions.postdocs", "n"),
                  ("of them hold a temporary visa",
                   "postdoc_citizenship", "named_institutions.foreign", "n")),
        note="An investigation was announced on this date. The federal "
             "postdoc survey counts what these nine institutions reported "
             "themselves, and the figures below are their own returns.",
        links=(("/postdocs#the-nine", "All nine, with their postdoc counts"),),
    ),
    Moment(
        t=434, who="Vice President JD Vance",
        quote="These universities are employing J1 visas for federally "
              "funded grants at a rate of about 61%. The national average is "
              "38%.",
        heading="The nine are at 60.7%. Nationally it is 58.3%.",
        note="The NSF Survey of Graduate Students and Postdoctorates puts "
             "the nine named universities at the share given from the "
             "podium. The same survey shows this is not confined to them: "
             "across every institution it covers, most postdoctoral "
             "appointments in the United States are held on a temporary "
             "visa. American citizens and permanent residents are a "
             "minority of the postdoctoral workforce nationally \u2014 in a "
             "workforce where roughly half the posts are paid for by federal "
             "research money. The nine are where the investigation starts, "
             "and the pattern runs through the whole system.",
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
        evidence=(("certified H-1B filings by firms meeting this site\u2019s "
                   "staffing-firm test", "visa_bodyshops",
                   "body_shop_totals.filings", "n"),
                  ("of all certified filings in the country",
                   "visa_bodyshops", "body_shop_totals.share_of_filings_pct",
                   "pct1"),
                  ("of all certified filings sit at the two lowest statutory "
                   "wage levels", "visa_bodyshops", "national.low_level_pct",
                   "pct1")),
        note="PERM is the mechanism described earlier as how an H-1B holder "
             "stays permanently. Suspension stops new and pending "
             "applications from these employers. It does not affect anyone "
             "already holding permanent residence.",
        links=(("/bodyshops", "What the filings show about these firms"),),
    ),
    Moment(
        t=757, who="Attorney General Todd Blanche",
        quote="This announcement today should send and does send a strong "
              "signal to every single employer in the United States that the "
              "Trump administration will not tolerate discrimination against "
              "American workers.",
        heading="The enforcement frame",
        evidence=(("permanent-residence filings by universities, FY2013\u2013FY2024",
                   "public_employer_perm", "sectors.universities.filings", "n"),
                  ("by public school districts", "public_employer_perm",
                   "sectors.school_districts.filings", "n")),
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
        note="No federal file records what happens in an office after a "
             "filing is certified. The disclosure files stop at the "
             "paperwork. Whether a displaced worker trained their "
             "replacement is exactly the kind of fact no agency collects, "
             "and that gap is itself the finding: the public record ends "
             "where the consequence begins.",
    ),
    Moment(
        t=1265, who="Labor Inspector General Anthony D\u2019Esposito",
        quote="Subpoenas have been served, investigations are underway, and "
              "nobody will be getting a free pass because their name is "
              "carved into an expensive building.",
        heading="The investigation is live",
        note="An investigation was opened, on the record, on this date. "
             "Its outcome will be whatever the investigators find. What "
             "this page supplies is the federal data the investigators and "
             "the public can both read now.",
    ),
    Moment(
        t=1316, who="Labor Inspector General Anthony D\u2019Esposito",
        quote="The Chinese Communist Party doesn't need to kick down the "
              "doors of America's research laboratories if our own "
              "institutions are willing to leave the doors wide open.",
        heading="The research-security argument",
        note="This site measures who is in the laboratories. In several "
             "strategic fields the graduate pipeline is overwhelmingly "
             "non-resident, and in a handful of programs every doctorate "
             "awarded in the window went to a non-resident. These are "
             "counts of degrees conferred, reported by the institutions "
             "themselves to the federal government.",
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
        evidence=(("research doctorates awarded in the window this site covers",
                   "critical_industries", "national.doctorates", "n"),
                  ("American universities whose dissertation record is "
                   "published here", "name_lists", "universities", "n"),
                  ("of them publish nothing a reader can search",
                   "repository_index", "without_repository", "n")),
        note="The last figure is the one worth acting on. No federal rule "
             "requires a university to publish a dissertation or even to "
             "list the ones it awarded, so the record of what American "
             "institutions produced had to be assembled one university at a "
             "time and remains a floor. A deposit requirement attached to "
             "federal research money would fix it.",
        links=(("/name-lists", "The dissertations themselves"),
               ("/data_requests#no-requirement", "The deposit requirement")),
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
             "occupations and wages were certified. Data about attempts to "
             "find American workers are not published by the relevant "
             "agencies. The recruitment an employer says it carried out "
             "before filing is attested on the form and never released, so "
             "no outside party can check it.",
        evidence=(("certified H-1B applications in the disclosure files",
                   "h1b_by_industry", "certified_filings", "n"),),
        links=(("/industries", "What was certified, by industry"),
               ("/query?sql=--%20What%20was%20certified%20as%20a%20speciality%20occupation%2C%20and%20at%20what%20wage.%0A--%20The%20lowest-paid%20certified%20occupations%2C%20by%20median%20offered%20wage.%0A--%20The%20wage%20here%20is%20what%20the%20employer%20OFFERED%20on%20the%20form%2C%20not%20what%0A--%20was%20paid%2C%20so%20any%20gap%20against%20the%20American%20rate%20is%20understated.%0ASELECT%20soc%2C%0A%20%20%20%20%20%20%20soc_title%2C%0A%20%20%20%20%20%20%20filings%2C%0A%20%20%20%20%20%20%20employers%2C%0A%20%20%20%20%20%20%20median_wage%2C%0A%20%20%20%20%20%20%20top_employer%0AFROM%20h1b_occupation%0AWHERE%20filings%20%3E%3D%20100%0AORDER%20BY%20median_wage%20ASC%0ALIMIT%2060", "The occupation and wage tables")),
    ),
)
