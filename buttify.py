import re
import math
import random
import hyphenate

WORD_REPLACE_FREQ = 1./11 # approx. how frequently should we butt
MAX_WEIGHT = 12 # = ~ 6 syllables
CONTEXTUAL_CHARS = 6 # six chars on either side (if possible)
BUTT = 'butt'

class Token(object):
    def __init__(self, start_pos, full_tok, is_whitespace):
        self.is_whitespace = is_whitespace
        self.start_pos = start_pos
        self.full_tok = full_tok
        self.hyphenated = None
    
    def is_suitable_token(self):
        """ Recognize a token (word+surrounding punctuation as suitable or not for replacement)
            Conditions:
                1) At least 2 word characters in a row
                2) Not a stopword
        """
        st = self.full_tok.strip()
        
        if not self.is_whitespace and len(st) > 2:
            if re.search(r"[a-zA-Z][a-zA-Z]+", st) is not None:
                if st.lower() not in STOPWORDS:
                    return True

        return False
    
    def hyphenate(self):
        self.hyphenated = hyphenate.hyphenate_word(self.full_tok)

def _load_stopwords(fname):
    """ Load a list of words unsuitable for replacement. """
    f = open(fname, 'r')
    stopwords = []
    
    for l in f:
        stopwords.append(l.strip())
    
    return stopwords

STOPWORDS = _load_stopwords('stopwords')

def split_by_whitespace(txt):
    """ Return txt split by whitespace, with the whitespace included in the returned array. """
    split_tokens = []
    last = 0
    
    for s in re.finditer(r"\s+", txt):
        sp = s.span()
        split_tokens.append(Token(last, txt[last:sp[0]], False))
        split_tokens.append(Token(sp[0], txt[sp[0]:sp[1]], True))
        last = sp[1]
    
    if last < len(txt):
        split_tokens.append(Token(last, txt[last:], False))
        
    return split_tokens

def replace_with_case(word, sub):
    """ Do a case-sensitive replacement (e.g., Latin -> Butt, hello -> butt, nUHH -> bUTT) """
    new_word = ''
    upper_count = 0
    
    for c, s in zip(word, sub):
        if c.isupper():
            new_word += s.upper()
            upper_count += 1
        else:
            new_word += s
    
    # don't forget to tack on the rest of the sub if the original word is shorter (so the zip wouldn't include it)
    if len(sub) > len(word):
        if upper_count == len(word) and len(word) > 1:
            sub = sub.upper()
        new_word += sub[len(word)-len(sub):]
    
    return new_word

def do_butt_sub(tok):
    """ Actually substitute the butt into a word by first breaking the word into syllables, and then finding a suitable syllable to substitute into. Returns the case of the replaced word as well as the meme location. """
    # hyphenate the word
    idxs = range(0, len(tok.hyphenated))
    
    while True:
        # choose which 'syllable' to sub
        idx = random.choice(idxs)
        idxs.remove(idx)
        # find the 'word' component in case of surrounding non-word
        s = re.match(r"([^ a-zA-Z]*)([a-zA-Z]+)(.*)", tok.hyphenated[idx])
        if s is not None and len(s.group(2)) > 0:
            pre = s.group(1)
            real_word = s.group(2)
            post = s.group(3)
            
            subbed_word = replace_with_case(real_word, BUTT)
            len_other_parts = sum([len(x) for x in tok.hyphenated[0:idx]])
            final_start_position = tok.start_pos+len_other_parts+len(pre)
            sub_length = len(real_word)
            
            # ugly substitutions
            # code is kinda hackish but seems to work
            # if the character following us in the string is the same as our ending character, move the index forward
            if len(post) == 0:
                tok_idx = final_start_position-tok.start_pos+sub_length
                while tok_idx < len(tok.full_tok) and tok.full_tok[tok_idx].lower() == BUTT[-1].lower() :
                    sub_length += 1
                    tok_idx += 1
            
            # or if the preceding character is the same, move it back
            if len_other_parts > 0 and len(pre) == 0:
                tok_idx = final_start_position-tok.start_pos
                while tok_idx > 0 and tok.full_tok[tok_idx].lower() == BUTT[0].lower():
                    final_start_position -= 1
                    tok_idx -= 1
            
            return (subbed_word, final_start_position, final_start_position+sub_length)
        elif len(idxs) == 0:
            return (None, -1)
        
def good_tokens(w_toks):
    """ Take a list of whitespace-separate tokens and return which are suitable for replacement """
    good_toks = []
    count = 0
    
    for i in range(len(w_toks)):        
        if w_toks[i].is_suitable_token():
            # weight the higher-syllable words to be replaced more often
            # but don't go nuts if someone has some long-ass string
            w_toks[i].hyphenate()
            good_toks += [i] * min((len(w_toks[i].hyphenated)*2), MAX_WEIGHT)
            count += 1
    
    return (good_toks, count)
    
def buttify_blip(txt):
    """ Return a list of location/correct-case pairs of subbed words. """
    toks = split_by_whitespace(txt)
    good, good_count = good_tokens(toks)
    num_to_replace = math.ceil(WORD_REPLACE_FREQ*good_count)
    #num_to_replace = random.randint(round(average_num_to_replace/1.3), round(average_num_to_replace*1.5))
    replace_pairs = []
    
    if num_to_replace > 0:
        # extract a random selection of words to buttify
        already_replaced = []
        i = 0
        while i < num_to_replace:
            idx = random.choice(good)
            # since higher-syllable words can be here a few times, ignore the ones we already did
            if len(already_replaced) == good_count:
                # uh-oh, bail out! failed to replace anything
                if len(replace_pairs) > 0:
                    break
                
                return None  
            elif idx in already_replaced:
                continue
                
            subbed_tok, start_pos, end_pos = do_butt_sub(toks[idx])
            already_replaced.append(idx) # even if it fails, we will ignore this token
            # make sure its at least CONTEXTUAL_CHARS away from other subbs (for good-looking-ness as well as delta removal)
            for itm in replace_pairs:
                # if too close, ignore the token
                if abs(start_pos-itm[2]) <= CONTEXTUAL_CHARS or abs(end_pos-itm[1]) <= CONTEXTUAL_CHARS:
                    subbed_tok = None
                    break
                    
            if subbed_tok is not None:
                # ok, grab some context so we can reverse the process if need be
                old_context = txt[max(0, start_pos-CONTEXTUAL_CHARS):min(len(txt), end_pos+CONTEXTUAL_CHARS)]
                new_context = txt[max(0, start_pos-CONTEXTUAL_CHARS):start_pos]+subbed_tok+txt[end_pos:min(len(txt), end_pos+CONTEXTUAL_CHARS)]
                replace_pairs.append((subbed_tok, start_pos, end_pos, old_context, new_context))
                i += 1
    
        replace_pairs.sort(cmp=lambda x,y: cmp(x[1], y[1]))
        return replace_pairs
    
    # no-op
    return None

if __name__ == '__main__':
    import sys
    rp = buttify_blip(sys.argv[1])
    print 'pairs: ', rp
    new_txt = ''
    last = 0
    for w,s,e in rp:
        new_txt += sys.argv[1][last:s]
        new_txt += w
        last = e
    
    if last < len(sys.argv[1]):
        new_txt += sys.argv[1][last:]
    
    print 'Result: ', new_txt