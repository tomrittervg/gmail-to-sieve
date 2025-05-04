#!/usr/bin/env python

import sys
from xml.dom import minidom

class UnknownEntry(Exception):
    pass
class UnhandledCase(Exception):
    pass

# Should dots in the folder name be replaced by dashes (for Dovecot)
REPLACE_FOLDER_DOTS=False
# Should slashes in the folder name be replaced by dots (for Dovecot)
REPLACE_FOLDER_SLASH=False
# Should slashes in the folder name be replaced by dots (for Infomaniak)
REMOVE_INBOX=True

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
    'shouldNeverMarkAsImportant' : 'a',
    'smartLabelToApply' : 'a',

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
    for criterion in criteria:
        this_criteria = ""
        #Simple From, To, or Subject Matching
        if criterion in ["from", "to", "subject"]:
            subcriteria = criteria[criterion].split(" OR ")
            this_criteria += "header :contains \"" + criterion + "\" "
            if len(subcriteria) > 1: this_criteria += "["
            this_criteria += "\"" + "\",\"".join(subcriteria) + "\""
            if len(subcriteria) > 1: this_criteria += "]"
        #Match a Mailing List
        elif criterion == "hasTheWord" and "list:" in criteria[criterion]:
            list_id = criteria[criterion].replace("list:", "").strip("('\")")
            this_criteria += "header :contains \"list-id\" \"" + list_id + "\""
        elif criterion == "hasTheWord":
            raise UnhandledCase("hasTheWord without a list: identifier")
        #Match a missing word
        elif criterion == "doesNotHaveTheWord":
            subcriteria = criteria[criterion].split(" OR ")
            this_criteria += "not body :text :contains "
            if len(subcriteria) > 1: this_criteria += "["
            this_criteria += "\"" + "\",\"".join(subcriteria) + "\""
            if len(subcriteria) > 1: this_criteria += "]"

        sieve_criteria.append(this_criteria)

    sieve_script += ", ".join(sieve_criteria)
    sieve_script += ")\n{\n"

    #===================================================================================================
    didAction = False
    for action in actions:
        if action == 'label':
            didAction = True
            folder = actions[action]
            if REPLACE_FOLDER_DOTS:
                folder = folder.replace(".", "-")
            if REPLACE_FOLDER_SLASH:
                folder = folder.replace("/", ".")
            if REMOVE_INBOX:
                folder = folder.replace("INBOX/", "")
            sieve_title = actions[action]
            sieve_script += "\tfileinto \"" + folder + "\";\n"
        elif action == 'shouldTrash':
            didAction = True
            sieve_script += "\tdiscard;\n"
        elif action == 'shouldMarkAsRead':
            didAction = True
            sieve_script += "\taddflag \"\\\\Seen\";\n"
        elif action == 'shouldAlwaysMarkAsImportant':
            didAction = True
            sieve_script += "\taddflag \"\\\\Flagged\";\n"
        elif action == 'shouldArchive':
            pass
        elif action == 'shouldNeverSpam':
            pass
        elif action == 'shouldNeverMarkAsImportant':
            pass
        elif action == 'smartLabelToApply':
            pass

    if not didAction:
        return "",""

    sieve_script += "}\n"
    if sieve_title:
        sieve_script = sieve_script.replace("XXX_REPLACEME_XXX", sieve_title)
    else:
        sieve_script = sieve_script.replace("# rule:[XXX_REPLACEME_XXX]\n", "")
    return sieve_script, folder

#===================================================================================================

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: " + sys.argv[0] + " input:filters.xml output:filters.sieve output:folderscript.sh")
        sys.exit()

    inputfile = sys.argv[1]
    xmldoc = minidom.parse(inputfile)

    filters = []
    for entry in xmldoc.getElementsByTagName("entry"):
        properties = {}
        for node in entry.childNodes:
            if node.nodeName == "apps:property":
                properties[node.getAttribute('name')] = node.getAttribute('value')
        filters.append(properties)

    sieveout = open(sys.argv[2], "w")
    bashout = open(sys.argv[3], "w")

    sieveout.write('require ["body","fileinto","imap4flags"];\n')

    folders  = set()
    unhandled = 0
    unhandled_criteria = set()
    for filter in filters:
        try:
            script, folder = filterToSieve(filter)
            sieveout.write(script)
            if folder:
                folders.add(folder)
        except UnknownEntry     :
            unhandled += 1
            unhandled_criteria.update(getFilterUnknown(filter))

    if len(folders) > 0:
        bashout.write("#!/bin/bash\n")
        for target_folder in folders:
            bashout.write('mkdir -p ".' + target_folder + '/new"\n')
            bashout.write('mkdir -p ".' + target_folder + '/tmp"\n')
            bashout.write('mkdir -p ".' + target_folder + '/cur"\n')
            bashout.write('touch ".' + target_folder + '/maildirfolder"\n')
        bashout.write('chown -R vmail:vmail .*')

    if unhandled > 0:
        print(unhandled, "filters were unable to be processed. The following unknown attributes were seen:", list(unhandled_criteria))


