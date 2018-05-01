import decimal
import re

import utils


def translate_row(row):
    """Translates a row of labeled data into CRF++-compatible tag strings.

    Args:
        row: A row of data from the input CSV of labeled ingredient data.

    Returns:
        The row of input converted to CRF++-compatible tags, e.g.

            2\tI1\tL4\tNoCAP\tNoPAREN\tB-QTY
            cups\tI2\tL4\tNoCAP\tNoPAREN\tB-UNIT
            flour\tI3\tL4\tNoCAP\tNoPAREN\tB-NAME
    """
    # extract the display name
    display_input = utils.cleanUnicodeFractions(row['input'])
    tokens = utils.tokenize(display_input)
    del (row['input'])

    rowData = _addPrefixes([(t, _matchUp(t, row)) for t in tokens])

    translated = ''
    for i, (token, tags) in enumerate(rowData):
        features = utils.getFeatures(token, i + 1, tokens)
        translated += utils.joinLine(
            [token] + features + [_bestTag(tags)]) + '\n'
    return translated


def _parseNumbers(s):
    """
    Parses a string that represents a number into a decimal data type so that
    we can match the quantity field in the db with the quantity that appears
    in the display name. Rounds the result to 2 places.
    """
    ss = utils.unclump(s)

    m3 = re.match('^\d+$', ss)
    if m3 is not None:
        return decimal.Decimal(round(float(ss), 2))

    m1 = re.match(r'(\d+)\s+(\d)/(\d)', ss)
    if m1 is not None:
        num = int(m1.group(1)) + (float(m1.group(2)) / float(m1.group(3)))
        return decimal.Decimal(str(round(num, 2)))

    m2 = re.match(r'^(\d)/(\d)$', ss)
    if m2 is not None:
        num = float(m2.group(1)) / float(m2.group(2))
        return decimal.Decimal(str(round(num, 2)))

    return None


def _matchUp(token, ingredientRow):
    """
    Returns our best guess of the match between the tags and the
    words from the display text.

    This problem is difficult for the following reasons:
        * not all the words in the display name have associated tags
        * the quantity field is stored as a number, but it appears
          as a string in the display name
        * the comment is often a compilation of different comments in
          the display name

    """
    ret = []

    # strip parens from the token, since they often appear in the
    # display_name, but are removed from the comment.
    token = utils.normalizeToken(token)
    decimalToken = _parseNumbers(token)

    # Note: We iterate in this specific order to preserve parity with the
    # legacy implementation. The legacy implementation is likely incorrect and
    # shouldn't actually include 'index', but we will revisit when we're ready
    # to change behavior.
    for key in ['index', 'name', 'qty', 'range_end', 'unit', 'comment']:
        val = ingredientRow[key]
        if isinstance(val, basestring):

            for n, vt in enumerate(utils.tokenize(val)):
                if utils.normalizeToken(vt) == token:
                    ret.append(key.upper())

        elif decimalToken is not None:
            if val == decimalToken:
                ret.append(key.upper())

    return ret


def _addPrefixes(data):
    """
    We use BIO tagging/chunking to differentiate between tags
    at the start of a tag sequence and those in the middle. This
    is a common technique in entity recognition.

    Reference: http://www.kdd.cis.ksu.edu/Courses/Spring-2013/CIS798/Handouts/04-ramshaw95text.pdf
    """
    prevTags = None
    newData = []

    for n, (token, tags) in enumerate(data):

        newTags = []

        for t in tags:
            p = "B" if ((prevTags is None) or (t not in prevTags)) else "I"
            newTags.append("%s-%s" % (p, t))

        newData.append((token, newTags))
        prevTags = tags

    return newData


def _bestTag(tags):

    if len(tags) == 1:
        return tags[0]

    # if there are multiple tags, pick the first which isn't COMMENT
    else:
        for t in tags:
            if (t != "B-COMMENT") and (t != "I-COMMENT"):
                return t

    # we have no idea what to guess
    return "OTHER"