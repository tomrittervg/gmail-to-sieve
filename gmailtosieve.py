#!/usr/bin/python

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
    return {p:v for p,v in properties.iteritems() if p in GMAIL_PROPERTIES and GMAIL_PROPERTIES[p] == 'c'}
def getFilterActions(properties):
    return {p:v for p,v in properties.iteritems() if p in GMAIL_PROPERTIES and GMAIL_PROPERTIES[p] == 'a'}
def getFilterUnknown(properties):
    return {p:v for p,v in properties.iteritems() if p not in GMAIL_PROPERTIES}

def filterToSieve(properties):
    criteria = getFilterCriteria(properties)
    actions = getFilterActions(properties)
    unknown = getFilterUnknown(properties)

    if len(unknown) >= 1:
        raise UnknownEntry("Identified the following unknown filter criteria:" + str(unknown))

    sieve_script = "if allof ("

    #===================================================================================================
    sieve_criteria = []
    for c in criteria:
        this_criteria = ""
        #Simple From, To, or Subject Matching
        if c in ["from", "to", "subject"]:
            this_criteria += "header :contains \"" + c + "\" [ \""
            this_criteria += "\", \"".join(criteria[c].split(" OR "))
            this_criteria += "\" ] "
        #Match a Mailing List
        elif c == "hasTheWord" and "list:" in criteria[c]:
            list_id = criteria[c].replace("list:", "").strip("('\")")
            this_criteria += "header :contains \"list-id\" \"" + list_id + "\""
        elif c == "hasTheWord":
            raise UnhandledCase("hasTheWord without a list: identifier")
        #Match a missing word
        elif c == "doesNotHaveTheWord":
            this_criteria += "not body :text :contains [ \""
            this_criteria += "\", \"".join(criteria[c].split(" OR "))
            this_criteria += "\" ] "

        sieve_criteria.append(this_criteria)

    sieve_script += " , ".join(sieve_criteria)
    sieve_script += ")\n{\n"

    #===================================================================================================
    for a in actions:
        if a == 'label':
            sieve_script += "\tfileinto \"" + actions[a] + "\";\n"
        elif a == 'shouldTrash':
            sieve_script += "\tdiscard;\n"
        elif a == 'shouldMarkAsRead':
            sieve_script += "\taddflag \"\\Seen\";\n"
        elif a == 'shouldAlwaysMarkAsImportant':
            sieve_script += "\taddflag \"\\Flagged\";\n"
        elif a == 'shouldArchive':
            pass
        elif a == 'shouldNeverSpam':
            pass

    sieve_script += "}\n"
    return sieve_script;

#===================================================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: " + sys.argv[0] + " filters.xml"
        sys.exit()

    filename = sys.argv[1]
    xmldoc = minidom.parse(filename)

    filters = []
    for p in xmldoc.getElementsByTagName("entry"):
        properties = {}
        for n in p.childNodes:
            if n.nodeName == "apps:property":
                properties[n.getAttribute('name')] = n.getAttribute('value')
        filters.append(properties)

    print 'require ["fileinto", "imap4flags", "body"];'

    unhandled = 0
    unhandled_criteria = set()
    for f in filters:
        try:
            print filterToSieve(f)
        except UnknownEntry     :
            unhandled += 1
            unhandled_criteria.update(getFilterUnknown(f))

    if unhandled > 0:
        print unhandled, "filters were unable to be processed. The following unknown attributes were seen:", list(unhandled_criteria)