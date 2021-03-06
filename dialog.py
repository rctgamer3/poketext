#!/usr/bin/env python
# -*- coding: utf-8 -*-
# アウエ

import itertools
import re
import pprint

def dist_merge(s1, s2):
    '''
    Calculate edit distance between two strings and what their
    'merged' value should be. This reduces errors when
    noise makes a character unrecognizable.
    '''
    dist = 0
    out = ''
    for a, b in itertools.izip_longest(s1, s2, fillvalue=' '):
        if a != ' ' and a != b:
            dist += 1
        if b != ' ':
            out += b
        else:
            out += a
    return dist, out


class BoxReader(object):
    '''Find each dialog box in the text version of the screen'''

    COORD_DIALOG = (0, 12, 19, 17)
    COORD_DIALOG_SMALL = (0, 14, 19, 17)
    COORD_DIALOG_PC = (0, 15, 19, 17)
    COORD_DIALOG_PC_CURRENT_BOX = (0, 0, 19, 3)
    COORD_DIALOG_PC_CURRENT_MON_NAME = (8, 2, 19, 13)
    banned_phrases = (
        'SAVE   \n',    # don't output the menu
    )

    def __init__(self, max_dist=3):
        self.last = ''
        self.lastline = ''
        self.group = []
        self.lastgroup = []
        self.dialog_handlers = []
        self.max_dist = max_dist
        self.continued = 0

    def add_dialog_handler(self, handler):
        self.dialog_handlers.append(handler)

    def handle_dialog(self, text, lines):
    #def handle_dialog(self, text, lines, timestamp):
        #print 'handle_dialog', repr(text), self.continued

        if text == '':  # dialog disappeared
            if self.last:
                self.group.append(self.last)
            if self.group and self.lastgroup and self.group[0] == self.lastgroup[-1]:
                # some screen effects make us lose the dialog temporarily
                # prevent duplicate lines this way
                self.group = []
            if self.group:
                out = ['']
                for el in self.group:
                    for line in el.splitlines():
                        if not line:
                            continue
                        dist, merged = dist_merge(out[-1], line)
                        if dist < self.max_dist:
                            out[-1] = merged
                        else:
                            out.append(line)
                out = ' '.join(out).strip()
                out = re.sub(r'\s+', ' ', out)
                out = re.sub(r'- ', '', out)
                for handler in self.dialog_handlers:
                    #handler(out, lines, timestamp)
                    handler(out, lines)
                self.lastgroup = self.group
                self.group = []
            self.last = text
            return
        text = text.replace(' ' * 18 + '\n', '')
        if text.strip() in ('', self.last.strip()):
            return
        dist, merged = dist_merge(self.last, text)
        if dist < self.max_dist:
            self.last = merged
        else:
            #print self.last.replace('\n', '`'), '--', text.replace('\n', '`')
            if self.last != self.lastline:
                self.group.append(self.last)
                self.last = text

    def handle(self, data):
        def conv_tile_or_text(t):
            if isinstance(t, int):
                return ' '
            if len(t) == 1:
                return t
            return t[1:]

        lines = data['full']
        lines = [map(conv_tile_or_text, lines[20 * i : 20 * i + 20]) for i in range(18)]
	#print lines
        #timestamp = data['timestamp']
        boxes = []

        for box_y in range(18):
            for box_x in range(20):
                if lines[box_y][box_x] == 'o':  # top left corner
                    # might be a dialog box, trace
                    top_x = box_x + 1
                    # top line
                    while top_x < 20 and lines[box_y][top_x] == '-':
                        top_x += 1
                    if top_x == 20 or lines[box_y][top_x] != 'o':   # top right
                        break
                    left_y = box_y + 1
                    # left + right lines
                    while left_y < 18 and lines[left_y][box_x] == '|' and lines[left_y][top_x] == '|':
                        left_y += 1
                    # bottom left/right corners
                    if left_y == 18 or lines[left_y][box_x] != 'o' or lines[left_y][top_x] != 'o':
                        break

                    box = ''
                    for y in xrange(box_y + 1, left_y):
                        for x in xrange(box_x + 1, top_x):
                            box += lines[y][x]
                        box += '\n'
                    boxes.append(((box_x, box_y, top_x, left_y), box))
        for coord, box in boxes:
	    #print coord, box
            if coord == self.COORD_DIALOG:
		#print 'BIG'
                #self.handle_dialog(box, lines, timestamp)
                self.handle_dialog(box, lines)
                break
	    elif coord == self.COORD_DIALOG_SMALL:
		#print "SMALL"
		self.handle_dialog(box, lines)
	    elif coord == self.COORD_DIALOG_PC:
		#print "PC TIME UGH NOOOO"
		self.handle_dialog(box, lines)
	    elif coord == self.COORD_DIALOG_PC_CURRENT_BOX:
		print "CURRENT SOMETHING OR CALL"
#		self.handle_dialog(box, lines)
#	    elif coord == self.COORD_DIALOG_PC_CURRENT_MON_NAME:
#		self.handle_dialog(box, lines)
            else:
                continue
                for banned_phrase in self.banned_phrases:
                    if banned_phrase in box:
                        break
                else:
                    print '%2d %2d %2d %2d' % coord, box.replace('\n', '`')
        else:
            #self.handle_dialog('', lines, timestamp)
            self.handle_dialog('', lines)

class BattleState(object):
    '''
    Track status (HP, LVL, etc) in a battle from the dialog and
    text on the screen
    '''

    re_wild = re.compile(r'Wild (.*) appeared')
    re_trainer = re.compile(r'(.*) wants to fight')
    re_enemy_faint = re.compile(r'Enemy .* fainted')
    re_opponent_level = re.compile(r'@(\d\d)')
    #re_opponent_gender = re.compile(r'@(.)')
    #re_opponent_gender = re.compile(r'@(.)')
    #re_opponent_gender = re.compile(r'(?:F|M)+')
    #re_opponent_gender = re.compile(ur'(?:\u2640|\u2642)+', re.UNICODE)
    re_opponent_gender = re.compile(ur'(?:\u2640|\u2642|\u0020)+', re.UNICODE)
    banned_phrases = ('Choose a POKeMON', 'already out', 'Come back', 'OAK:',
            'which POKéMON', 'Which ᵖᵏᵐᶰ', 'will to fight', 'catchy tune', 'about to use', 'change POKéMON',
            'no running from', 'Thats too impor', 'Waiting!')

    STATE_NORMAL = 0
    STATE_WILD_BEATEN = 1

    #def __init__(self, start_text, timestamp):
    def __init__(self, start_text):
        self.last_hp = (0, 0, 0)
        m_wild = self.re_wild.match(start_text)
        m_trainer = self.re_trainer.match(start_text)
        self.trainer_battle = m_trainer is not None
        if m_trainer:
            self.opponent = m_trainer.group(1)
        else:
            self.opponent = m_wild.group(1)
        #self.start_time = timestamp
        #self.lines = [(timestamp, start_text)]
        self.lines = [(start_text)]
        self.state = self.STATE_NORMAL
        self.opponent_level = 0
        #self.opponent_gender = 0

    def read_hp(self, lines):
        my_hp_bar = ''.join(lines[10][11:18]).split('/')
        my_hp_cur, my_hp_tot = int(my_hp_bar[0]), int(my_hp_bar[1])
        enemy_hp_bar = ''.join(lines[2][2:10])
        if not re.match(r'HPP:([_=1-7]H)*', enemy_hp_bar):
            raise ValueError
        enemy_hp_perc = int(sum(0 if c == '_' else 8 if c == '=' else int(c) for c in enemy_hp_bar[4::2])*100/48.)
        return my_hp_cur, my_hp_tot, enemy_hp_perc

    def read_enemy_level(self, lines):
        try:
            opp_level = lines[1][6:9]
            if opp_level[0] == 'Lv':
                return int(opp_level[1]+opp_level[2])
            return 0
        except ValueError:
            return 0

    def read_enemy_gender(self, lines):
        try:
            opp_gender = lines[1][9]
	    #pprint.pprint(opp_gender)
	    #pprint.pprint(opp_gender[0])
	    #pprint.pprint(lines[1][6:9])
            if opp_gender == u'\u2640':
                print "\u2640"
                return "♀"
	    elif opp_gender == u'\u2642':
                print "\2642"
		return "♂"
            elif opp_gender == u'\u0020':
		print "UNDEFINED EnGen"
                return "N/A"
            else:
                return '???'
        except ValueError:
            return '0'

    #def feed(self, text, lines, timestamp):
    def feed(self, text, lines):
        '''
        handle a new line of dialog
        returns True if it's the end of an encounter
        '''
        if self.state == self.STATE_WILD_BEATEN:
            # our opponent has fainted, but we might have EXP gain lines
            if 'Exp' not in text:
                return True

        text = self.annotate(text, lines)

        for banned in self.banned_phrases:
            if banned in text:
                break
        else:
            self.lines.append((text))

        if 'whited out' in text:
            return True
        if self.trainer_battle:
            if 'for winning' in text:
                return True
        else:
            if 'was caught' in text or 'away' or 'was sent to BILL' in text:
                return True
            if self.re_enemy_faint.search(text):
                self.state = self.STATE_WILD_BEATEN

    def annotate(self, text, lines):
        '''
        Add useful context (levels, damage amounts) to a line of dialog
        '''
        if self.re_wild.match(text) or self.re_trainer.match(text):
	    print "WILD OR TRAINER"
            self.opponent_level = 0
	    self.opponent_gender = 'N/A'
            #self.opponent_gender = 0

#        if 'Bye,' in text:
#	   text = re.sub(r'Bye, ( \S*!)$' % text)

        if 'sent out' in text:
	    print "SENT OUT!"
            level = self.read_enemy_level(lines)
            if level:
                text = re.sub(r'sent out ( \S*!)$', r'sent out L%02d\1' % level, text)
#        if self.opponent_gender == 0:
#            self.opponent_gender = self.read_enemy_gender(lines)
#            if self.opponent_gender:
#                text += ' EnGend:%s' % self.opponent_gender
        if self.opponent_level == 0:
            self.opponent_level = self.read_enemy_level(lines)
            self.opponent_gender = self.read_enemy_gender(lines)
	    #print "self.opponent_level", self.opponent_level
            #pprint.pprint(lines[1][9])
            #pprint.pprint(lines[1][9:10])
            #pprint.pprint(lines[1][10])
            #pprint.pprint(self.opponent_gender)
	    #print "self.opponent_gender", self.opponent_gender
            if self.opponent_level:
		#print self.opponent_level, self.opponent_gender
                text += ' [EnLvl: %d, EnGend: %s]' % (self.opponent_level, unicode(self.opponent_gender, 'utf-8'))
	    if self.opponent_level and self.opponent_gender == 'N/A':
		print "UNKNOWN GENDER PRINT ANYWAY"
                text += ' [EnLvl: %d, EnGend: N/A]' % self.opponent_level

        try:
            hp = self.read_hp(lines)
        except (ValueError, IndexError):
	    #print hp
            hp = self.last_hp

        ext = ''
        if hp != self.last_hp:
            if hp[2] != self.last_hp[2]:
                ext += ' En: %d%% (%d%%)' % (hp[2], hp[2]-self.last_hp[2])
            if hp[0] != self.last_hp[0] and hp[1] == self.last_hp[1]:
                ext += ' Us: %d/%d (%d)' % (hp[0], hp[1], hp[0]-self.last_hp[0])
            self.last_hp = hp
	print "EXT START"
	print ext
	print "return"
        return text + ext
	print "EXT STOP"
    def __str__(self):
        out = ''
        if self.trainer_battle:
            #out += 'Trainer battle with %s at %s\n' % (self.opponent, self.start_time)
            out += 'Trainer battle with %s\n' % (self.opponent)
        else:
            out += 'Wild encounter with L%02d %s\n' % (self.opponent_level, self.opponent)
            #out += 'Wild encounter with L%02d %s at %s\n' % (self.opponent_level, self.opponent, self.start_time)
        #for timestamp, text in self.lines[1:]:
            #out += '   %-14s %s\n' % (timestamp, text)
        for text in self.lines[1:]:
            out += '   %s\n' % (text)
        return out
