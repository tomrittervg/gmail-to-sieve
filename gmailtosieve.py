#!/usr/bin/env python

import sys
from xml.dom import minidom

class UnknownEntry(Exception):
    pass
class UnhandledCase(Exception):
    pass

GMAIL_PROPERTIES = {
    #Criteria
    'to' : 'c',
    'from' : 'c',
    'hasTheWord' : 'c',
    'doesNotHaveTheWord' : 'c',
    'subject' : 'c',

    #Actions
    'label' : 'a',
    'shouldTrash' : 'a',
    'shouldAlwaysMarkAsImportant' : 'a',
    'shouldNeverSpam' : 'a',
    'shouldMarkAsRead' : 'a',
    'shouldArchive' : 'a',

    #Ignore (What _are_ these?)
    'sizeUnit' : 'i',
    'sizeOperator' : 'i',    
}

def getFilterCriteria(properties):
    return {p:v for p,v in properties.items() if p in GMAIL_PROPERTIES and GMAIL_PROPERTIES[p] == 'c'}
def getFilterActions(properties):
    return {p:v for p,v in properties.items() if p in GMAIL_PROPERTIES and GMAIL_PROPERTIES[p] == 'a'}
def getFilterUnknown(properties):
    return {p:v for p,v in properties.items() if p not in GMAIL_PROPERTIES}

def filterToSieve(properties):
    criteria = getFilterCriteria(properties)
    actions = getFilterActions(properties)
    unknown = getFilterUnknown(properties)

    if len(unknown) >= 1:
        raise UnknownEntry("Identified the following unknown filter criteria:" + str(unknown))

    folder = None
    sieve_title = ""
    sieve_script  = "# rule:[XXX_REPLACEME_XXX]\n"
    sieve_script += "if allof ("

    #===================================================================================================
    sieve_criteria = []
    for c in criteria:
        this_criteria = ""
        #Simple From, To, or Subject Matching
        if c in ["from", "to", "subject"]:
            subcriteria = criteria[c].split(" OR ")
            this_criteria += "header :contains \"" + c + "\" "
            if len(subcriteria) > 1: this_criteria += "["
            this_criteria += "\"" + "\",\"".join(subcriteria) + "\""
            if len(subcriteria) > 1: this_criteria += "]"
        #Match a Mailing List
        elif c == "hasTheWord" and "list:" in criteria[c]:
            list_id = criteria[c].replace("list:", "").strip("('\")")
            this_criteria += "header :contains \"list-id\" \"" + list_id + "\""
        elif c == "hasTheWord":
            raise UnhandledCase("hasTheWord without a list: identifier")
        #Match a missing word
        elif c == "doesNotHaveTheWord":
            subcriteria = criteria[c].split(" OR ")
            this_criteria += "not body :text :contains "
            if len(subcriteria) > 1: this_criteria += "["
            this_criteria += "\"" + "\",\"".join(subcriteria) + "\""
            if len(subcriteria) > 1: this_criteria += "]"

        sieve_criteria.append(this_criteria)

    sieve_script += ", ".join(sieve_criteria)
    sieve_script += ")\n{\n"

    #===================================================================================================
    didAction = False
    for a in actions:
        if a == 'label':
            didAction = True
            folder = actions[a].replace(".", "-").replace("/", ".")
            sieve_title = actions[a]
            sieve_script += "\tfileinto \"" + folder + "\";\n"
        elif a == 'shouldTrash':
            didAction = True
            sieve_script += "\tdiscard;\n"
        elif a == 'shouldMarkAsRead':
            didAction = True
            sieve_script += "\taddflag \"\\\\Seen\";\n"
        elif a == 'shouldAlwaysMarkAsImportant':
            didAction = True
            sieve_script += "\taddflag \"\\\\Flagged\";\n"
        elif a == 'shouldArchive':
            pass
        elif a == 'shouldNeverSpam':
            pass

    if not didAction:
        return "",""

    sieve_script += "}\n"
    if sieve_title:
        sieve_script = sieve_script.replace("XXX_REPLACEME_XXX", sieve_title)
    else:
        sieve_script = sieve_script.replace("# rule:[XXX_REPLACEME_XXX]\n", "")
    return sieve_script.encode('utf-8'), folder

#===================================================================================================

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: " + sys.argv[0] + " input:filters.xml output:filters.sieve output:folderscript.sh")
        sys.exit()

    inputfile = sys.argv[1]
    xmldoc = minidom.parse(inputfile)

    filters = []
    for p in xmldoc.getElementsByTagName("entry"):
        properties = {}
        for n in p.childNodes:
            if n.nodeName == "apps:property":
                properties[n.getAttribute('name')] = n.getAttribute('value')
        filters.append(properties)

    sieveout = open(sys.argv[2], "w")
    bashout = open(sys.argv[3], "w")

    sieveout.write('require ["body","fileinto","imap4flags"];\n')

    folders  = set()
    unhandled = 0
    unhandled_criteria = set()
    for f in filters:
        try:
            script, folder = filterToSieve(f)
            sieveout.write(script)
            if folder:
                folders.add(folder)
        except UnknownEntry     :
            unhandled += 1
            unhandled_criteria.update(getFilterUnknown(f))

    if len(folders) > 0:
        bashout.write("#!/bin/bash\n")
        for i in folders:
            bashout.write('mkdir -p ".' + i + '/new"\n')
            bashout.write('mkdir -p ".' + i + '/tmp"\n')
            bashout.write('mkdir -p ".' + i + '/cur"\n')
            bashout.write('touch ".' + i + '/maildirfolder"\n')
        bashout.write('chown -R vmail:vmail .*')

    if unhandled > 0:
        print(unhandled, "filters were unable to be processed. The following unknown attributes were seen:", list(unhandled_criteria))


