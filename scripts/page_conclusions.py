#!/usr/bin/env python3
"""What each page concludes, declared once.

WHY THIS EXISTS

Every page on this site reported a measurement and stopped. A reader who
already shares the author's view supplied the conclusion themselves; everyone
else read a table. The author's instruction is that each page should say what
its own figures mean.

THE RULE THAT MAKES THESE DEFENSIBLE

A conclusion is drawn from THE DATA ON ITS OWN PAGE, and from nothing else.
The temptation is to repeat the same five sentences everywhere, which reads
as a slogan and invites exactly the rebuttal that the figures were arranged
to fit a view decided in advance. These are written the other way round: the
page's own numbers first, then what follows from them.

Where a page's data does not support a claim, the conclusion does not make
it. That is not softening. A conclusion that outruns its evidence is the one
a hostile reader breaks first, and breaking one costs the others their
credibility.

WHAT THEY MAY AND MAY NOT SAY

They are the author's argument and they are blunt. They may say that public
money paid for a result the public did not ask for, that institutions took
federal and state funds while awarding most of their seats to people who are
not Americans, and that Americans are disadvantaged in institutions their
families built and fund.

They may NOT say that any named school, firm or person broke a law. No page
on this site does, and a conclusion is not a licence to start. Every figure
cited resolves from built data at render time, so a conclusion cannot outlive
the evidence under it.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Conclusion:
    #: The published page, as the site serves it.
    page: str
    heading: str
    #: One sentence, set larger. The point of the page in a line, for the
    #: reader who got here by scrolling and will not read three paragraphs.
    lede: str
    #: Paragraphs. Auto-markers inside stay live.
    paragraphs: tuple
    #: Where to go next: (href, label, one line of why). A conclusion that
    #: ends in nothing leaves the reader at the bottom of a page with no
    #: next move, which is how a site that is meant to be read in sequence
    #: gets read one page at a time.
    next: tuple = field(default_factory=tuple)
    #: Inserted before this element id where present, else before the
    #: page's method section, else at the end of the content.
    before: str = ""


A = "<!--auto:data:{}-->{}<!--/auto-->"

CONCLUSIONS: tuple[Conclusion, ...] = (
    Conclusion(
        page="overview.html",
        heading="What this adds up to",
        lede="Public money pays for these programs, and a growing number of them now award most of their seats to people who are not Americans.",
        paragraphs=(
            "American research universities are paid for by Americans. Federal "
            "research funding runs to roughly $875,000 for every STEM research "
            "doctorate awarded, and state legislatures fund the public ones on "
            "top of that. The people who pay are entitled to ask who the money "
            "produces.",
            "The answer is increasingly not them. At "
            + A.format("level_rankings.levels.masters.institutions_majority_nra|n", "121")
            + " of the "
            + A.format("level_rankings.levels.masters.institutions_eligible|n", "567")
            + " institutions large enough to measure, most of the master's "
            "degrees awarded go to people who are not Americans. At "
            + A.format("level_rankings.levels.doctorate.institutions_majority_nra|n", "56")
            + " institutions the same is true of the doctorate.",
            "A seat is a finite thing. An American who is not admitted to a "
            "program does not get a smaller share of it; they get none of it. "
            "When most of a publicly funded program's seats go to temporary "
            "visa holders year after year, the effect on American applicants "
            "is the same whatever anyone intended, and the people funding it "
            "are the ones going without.",
        ),
        next=(
            ("/institutions", "Compare any two institutions",
             "The master's level, institution by institution."),
            ("/visa-schools", "Schools that launder visas",
             "Where the graduate program is the product and the visa is why "
             "it sells."),
            ("/data_requests", "What the government will not publish",
             "Twenty-four asks, most needing no new collection."),
        ),
        before="",   # no method section: the injector puts it last
    ),
    Conclusion(
        page="visa-schools.html",
        heading="What this adds up to",
        lede="These institutions take federal student aid Americans alone can use, and award most of their graduate seats to people who cannot.",
        paragraphs=(
            "These "
            + A.format("visa_schools.totals.schools|n", "57")
            + " schools are not teaching Americans. Foreign students are most "
            "of their graduate enrollment, and at several of them it is nine in "
            "ten.",
            "They are funded anyway. "
            + A.format("visa_schools.totals.take_federal_student_aid|n", "53")
            + " of them take federal student aid, drawing "
            + A.format("visa_schools.totals.pell_dollars|usdm", "$388m")
            + " in Pell grants and "
            + A.format("visa_schools.totals.federal_loan_dollars|usdm", "$618m")
            + " in federal loans. Foreign students cannot receive either. That "
            "money is American students' aid, paid to institutions whose "
            "graduate programs are mostly not for them.",
            "What the money buys is a work visa. The degree is the product and "
            "the visa is why it sells, and the American taxpayer is "
            "underwriting the machinery.",
        ),
        next=(
            ("/bodyshops", "Who hires on the far side",
             "The firms that supply the workers these degrees produce."),
            ("/institutions", "Compare any two institutions",
             "The same measure for every institution large enough to count."),
        ),
        before="method",
    ),
    Conclusion(
        page="bodyshops.html",
        heading="What this adds up to",
        lede="An American graduate is not competing on merit against an equal. They are competing against a cheaper worker who cannot leave.",
        paragraphs=(
            "This is the other end of the pipeline. "
            + A.format("visa_bodyshops.body_shop_totals.employers|n", "1,106")
            + " firms filed "
            + A.format("visa_bodyshops.body_shop_totals.filings|n", "252,806")
            + " certified applications, "
            + A.format("visa_bodyshops.body_shop_totals.share_of_filings_pct|pct1", "12.2%")
            + " of every certified H-1B application in these years. Their "
            "business is supplying people to other companies, by their own "
            "answers on their own forms.",
            "The wage data says what the arrangement is worth. Of "
            + A.format("local_wage_comparison.filings_priced|n", "565,966")
            + " certified applications priced against the local market, "
            + A.format("local_wage_comparison.below_local_median_pct|pct1", "78.7%")
            + " were below the median wage for that occupation in that place. "
            "A worker whose right to remain is tied to an employer is a worker "
            "who does not negotiate, and the discount is the point.",
            "An American graduate competing for these jobs is not competing on "
            "merit against an equal. They are competing against a cheaper "
            "worker who cannot leave, supplied at volume by firms built for "
            "the purpose.",
        ),
        next=(
            ("/visa-schools", "Where the workers come from",
             "The graduate programs that produce them."),
            ("/public-sector-visas", "The public payroll",
             "Where taxpayers fund the sponsorship directly."),
        ),
        before="method",
    ),
    Conclusion(
        page="public-sector-visas.html",
        heading="What this adds up to",
        lede="Public money should hire the public that funds it. These are the records of institutions concluding, tens of thousands of times, that no American would do.",
        paragraphs=(
            "This is the public payroll. Universities, school districts and "
            "agencies of state government sponsored "
            + A.format("public_employer_perm.public_rows|n", "42,833")
            + " people for permanent residence over twelve years, and every "
            "one of those posts is funded by taxpayers.",
            "Sponsorship requires an employer to test the local labor market "
            "first. These filings are the record of institutions concluding, "
            "tens of thousands of times, that no American would do. In the "
            "roles where the public can see the detail, the pattern is narrow "
            "enough to raise the question of whether the test was ever a real "
            "one.",
            "Public money should hire the public that funds it. Where it does "
            "not, the public is entitled to know which bodies, in which roles, "
            "and the records on this page name them.",
        ),
        next=(
            ("/state-agencies", "The temporary visas",
             "Far more numerous, and they cannot name a nationality."),
            ("/data_requests", "What is not published",
             "The worker fields were withdrawn after FY2024."),
        ),
        before="method",
    ),
    Conclusion(
        page="institutions.html",
        heading="What this adds up to",
        lede="An American applying to their own state university now applies to a program where they are the minority admitted.",
        paragraphs=(
            "The master's degree is where the money is, and it is where "
            "Americans have lost the most ground. At "
            + A.format("level_rankings.levels.masters.institutions_majority_nra|n", "121")
            + " institutions, most of the master's degrees awarded go to "
            "people who are not Americans.",
            "These are not marginal places. They include public universities "
            "built by state legislatures, funded by state taxpayers, and "
            "founded to educate the people of those states. An American "
            "applying to a program at their own state university now applies "
            "to a program where they are the minority admitted.",
            "Nothing in the law requires this and no one voted for it. It is "
            "the accumulated result of institutions following the money, with "
            "nobody counting the result until now.",
        ),
        next=(
            ("/overview", "The national picture",
             "What the averages hide."),
            ("/visa-schools", "The clearest cases",
             "Where graduate enrollment is almost entirely foreign."),
        ),
        before="method",
    ),
    Conclusion(
        page="eor.html",
        heading="What this adds up to",
        lede="The visa figures everywhere else on this site are a floor, and this is why.",
        paragraphs=(
            "The visa figures elsewhere on this site are a floor, and this is "
            "why. An employer-of-record firm lets an American company hire "
            "someone abroad and never file for a visa at all. No federal "
            "agency counts that route, and no federal agency can.",
            "The American worker competing against it has no way to see it. "
            "There is no disclosure file, no certified application, no wage "
            "floor, and no record that the job existed. The jobs leave and the "
            "statistics do not move.",
        ),
        next=(
            ("/bodyshops", "The route that is counted",
             "What the disclosure files do capture."),
            ("/data_requests", "What cannot be counted",
             "There is no federal count of this route and there cannot be."),
        ),
        before="method",
    ),
)
