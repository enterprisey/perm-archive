#!/usr/bin/env python
# vim: sw=4 ts=4 et ai

import cgitb; cgitb.enable()

import cgi
import datetime
import json
import os
import re
from string import Template
import sys
import urllib

import mwclient

TOOL_DIR = "."
#TOOL_DIR = "/data/project/apersonbot/public_html/perm-archive/"

ARCH_PFX = "Wikipedia:Requests for permissions/"

MONTHS = [ "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December" ]
PERM_PAGES = {
    "AutoWikiBrowser": "awb",
    "Autopatrolled": "apt",
    "Confirmed": "con",
    "File mover": "fm",
    "New page reviewer": "npr",
    "Page mover": "pm",
    "Pending changes reviewer": "pcr",
    "Rollback": "rb",
    "Account creator": "acc",
    "Event coordinator": "evt",
    "Extended confirmed": "ec",
    "Mass message sender": "mms",
    "Template editor": "te"
}
AWB_PERM_PG = "Wikipedia talk:AutoWikiBrowser/CheckPage"

APPROVED = 1
DENIED = 2
BOTH = APPROVED | DENIED

HDR_RGX = re.compile(r"^== (\w+) (\d\d?) ==$")
ARCH_LINE_RGX = re.compile(r"^\*\{\{Usercheck-short\|(.+)\}\} \[\[(.+)\]\] <sup>\[(\S+) link\]</sup>$")

def perm_page_to_code(page):
    perm1 = PERM_PAGES[page[35:]]
    if perm1: return perm1
    perm2 = "awb" if page == AWB_PERM_PG else ""
    if perm2: return perm2
    return ""

def perm_code_to_name(code):
    return next(key for key, value in PERM_PAGES.items() if value == code)

def parse_archive_wikitext(wikitext, users, perms):
    current_day = 0
    lines = []
    for each_line in wikitext.splitlines():
        if len(each_line.strip()) == 0: continue
        hdr_m = HDR_RGX.match(each_line)
        if hdr_m:
            current_day = int(hdr_m[2])
        else:
            line_m = ARCH_LINE_RGX.match(each_line)
            if line_m:
                perm = perm_page_to_code(line_m[2])
                if (not users or line_m[1] in users) and\
                        (not perms or perm in perms):
                    lines.append((current_day, line_m[1], perm, line_m[3]))
            else:
                raise ValueError("lel")
    return lines

def format_line(line):
    return "<tr><td>{}</td><td>{}</td><td class='{}'><a href='{}'>{}</a></td></tr>"

def main():
    page_template = None
    try:
        with open(os.path.join(TOOL_DIR, "template.txt")) as template_file:
            page_template = Template(template_file.read())
    except IOError as error:
        print("<h1>Search Error!</h1><p>I couldn't read the web template.<br /><small>Details: " + str(error) + "</small>")
        sys.exit(0)

    def error_and_exit(error):
        print(page_template.substitute(content="<p class='error'>{}</p>".format(error)))
        sys.exit(0)

    form = cgi.FieldStorage()
    if "users" in form:
        try:
            users = list(map(lambda s: s.strip(), form["users"].value.split("\n")))
        except:
            error_and_exit("Users should be one per line.")
    else: users = []
    users = tuple(users)

    outcome = 0
    try:
        outcome_val = form["outcome"].value
    except:
        error_and_exit("Error parsing provided 'Outcome' value.")
    if outcome_val == "any": outcome = BOTH
    elif outcome_val == "approved": outcome = APPROVED
    elif outcome_val == "denied": outcome = DENIED
    else: error_and_exit("Invalid value for 'Outcome': " + str(outcome_val))

    if "perms" in form:
        try:
            perms = list(map(lambda p: p.value, form["perms"]))
        except:
            error_and_exit("Error parsing provided 'Permissions' value.")
    else: perms = []
    perms = tuple(perms)

    YYYY_MM_RGX = re.compile("(\d\d\d\d)-(\d\d)")

    if "start" in form:
        start_match = YYYY_MM_RGX.match(form["start"].value)
        if start_match:
            start = (int(start_match[1]), int(start_match[2]))
        else:
            error_and_exit("Please provide 'Start' in YYYY-MM format.")
    else:
        error_and_exit("Please provide a 'Start' value.")

    if "end" in form:
        end_match = YYYY_MM_RGX.match(form["end"].value)
        if end_match:
            end = (int(end_match[1]), int(end_match[2]))
        else:
            error_and_exit("Please provide 'End' in YYYY-MM format.")
    else:
        error_and_exit("Please provide a 'End' value.")

    old_start = start
    start = min(start, end)
    end = max(old_start, end)

    years = list(range(start[0], end[0] + 1))
    full_months = []
    curr = list(start)
    #error_and_exit("<p>" + str(start) + "," + str(end) + "</p>")
    while tuple(curr) <= end:
        full_months.append(curr[:])
        curr[1] += 1
        if curr[1] >= 13:
            curr[1] = 1
            curr[0] += 1
    full_months = list(map(lambda ym: MONTHS[ym[1]-1] + " " + str(ym[0]), full_months))

    titles = []
    if outcome & APPROVED:
        titles.extend(list(map(lambda my: (ARCH_PFX + "Approved/" + my, APPROVED, my), full_months)))
    if outcome & DENIED:
        titles.extend(list(map(lambda my: (ARCH_PFX + "Denied/" + my, DENIED, my), full_months)))

    content = ("<table id='result' data-sortable><thead><tr><th>Date</th><th>User</th><th>Permission</th><th>Result</th></tr></thead><tbody>")
    site = mwclient.Site("en.wikipedia.org")
    for (each_title, outcome, my) in titles:
        each_page = site.pages[each_title]
        outcome_text = "approved" if (outcome & APPROVED) else "denied" 
        if each_page.exists:
            for each_line in parse_archive_wikitext(each_page.text(), users, perms):
                content += ("<tr><td>{} {}</td><td>{}</td><td>{}</td><td class='{}'><a href='{}'>{}</a></td></tr>"
                    .format(each_line[0], my, each_line[1], perm_code_to_name(each_line[2]), outcome_text, each_line[3], outcome_text))
    content += "</tbody></table>"
    
    print(page_template.substitute(content=content))

main()
