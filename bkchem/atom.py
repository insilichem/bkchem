#--------------------------------------------------------------------------
#     This file is part of BKchem - a chemical drawing program
#     Copyright (C) 2002-2004 Beda Kosata <beda@zirael.org>

#     This program is free software; you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation; either version 2 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     Complete text of GNU GPL can be found in the file gpl.txt in the
#     main directory of the program

#--------------------------------------------------------------------------


"""home for atom class"""

from __future__ import division

from math import atan2, sin, cos, pi, sqrt
import misc
import geometry
from warnings import warn
from ftext import ftext
import dom_extensions
import xml.dom.minidom as dom
import operator
import tkFont
from oasa import periodic_table as PT
import groups_table as GT
import marks
from parents import meta_enabled, area_colored, point_drawable
from parents import text_like, child_with_paper
from special_parents import vertex_common
import data
import re
import debug
import types

import oasa
from singleton_store import Screen


### NOTE: now that all classes are children of meta_enabled, so the read_standard_values method
### is called during their __init__ (in fact meta_enabled.__init__), therefor these values are
### not set in __init__ itself


### Class ATOM --------------------------------------------------
class atom( meta_enabled, area_colored, point_drawable, text_like,
            child_with_paper, vertex_common, oasa.atom):
  # note that all children of simple_parent have default meta infos set
  # therefor it is not necessary to provide them for all new classes if they
  # don't differ



  object_type = 'atom'
  # these values will be automaticaly read from paper.standard on __init__
  meta__used_standard_values = ['line_color','area_color','font_size','font_family']
  # undo meta infos
  meta__undo_fake = ('text',)
  meta__undo_simple = ()
  meta__undo_properties = area_colored.meta__undo_properties + \
                          point_drawable.meta__undo_properties + \
                          text_like.meta__undo_properties + \
                          vertex_common.meta__undo_properties + \
                          ( 'z', 'show', 'name', 'molecule', 'charge', 'show_hydrogens',
                            'pos', 'multiplicity', 'valency', 'free_sites')
  meta__undo_copy = vertex_common.meta__undo_copy + ('_neighbors',)
  meta__undo_children_to_record = vertex_common.meta__undo_children_to_record


  meta__configurable = {'show': (None, str),
                        'show_hydrogens': (int, str),
                        'charge': (int, str)
                        }


  def __init__( self, standard=None, xy = (), package = None, molecule = None):
    meta_enabled.__init__( self, standard=standard)
    vertex_common.__init__( self)
    self.molecule = molecule
    if xy:
      oasa.atom.__init__( self, coords=(xy[0],xy[1],0))
    else:
      oasa.atom.__init__( self)
    point_drawable.__init__( self)
    # hidden
    self.__reposition_on_redraw = 0

    # presentation attrs
    self.selector = None
    self._selected = 0 #with ftext self.selector can no longer be used to determine if atom is selected
    self.item = None
    self.ftext = None

    self.pos = None
    self.focus_item = None

    # chemistry attrs
    self.show_hydrogens = 0
    self.show = 0

    self.multiplicity = 1
    # used only for monitoring when undo is necessary, it does not always correspond to the atom name
    # only in case of self.show == 1
    self.text = ''

    if package:
      self.read_package( package)
    else:
      self.set_name( 'C')



  ## ---------------------------------------- PROPERTIES ------------------------------
      
  # molecule
  def _get_molecule( self):
    return self.__molecule

  def _set_molecule( self, mol):
    self.__molecule = mol

  molecule = property( _get_molecule, _set_molecule)


  # x
  def _get_x( self):
    return self.__x

  def _set_x( self, x):
    self.__x = Screen.any_to_px( x)

  x = property( _get_x, _set_x)


  # y
  def _get_y( self):
    return self.__y

  def _set_y( self, y):
    self.__y = Screen.any_to_px( y)

  y = property( _get_y, _set_y)


  # z
  def _get_z( self):
    return self.__z or 0

  def _set_z( self, z):
    self.__z = z

  z = property( _get_z, _set_z)


  # name
  def _get_name( self):
    return self.symbol

  def _set_name( self, name):
    try:
      t = unicode( name)
    except UnicodeDecodeError:
      t = name.decode( 'utf-8')
    self.symbol = t.encode('utf-8')
    self.dirty = 1
    #self.show = int( self.symbol != 'C')

  name = property( _get_name, _set_name)


  # show
  def _get_show( self):
    return self.__show

  def _set_show( self, show):
    if show in data.booleans:
      self.__show = data.booleans.index( show)
    else:
      self.__show = int( show)
    self.dirty = 1
    self.__reposition_on_redraw = 1

  show = property( _get_show, _set_show, None,
                   "should the atom symbol be displayed? accepts both 0|1 and yes|no")


  # show_hydrogens
  def _get_show_hydrogens( self):
    return self.__show_hydrogens

  def _set_show_hydrogens( self, show_hydrogens):
    if show_hydrogens in data.on_off:
      self.__show_hydrogens = data.on_off.index( show_hydrogens)
    else:
      self.__show_hydrogens = int( show_hydrogens)
    if self.__show_hydrogens:
      self.show = 1  # hydrogens imply showing the symbol
    self.dirty = 1
    self.__reposition_on_redraw = 1

  show_hydrogens = property( _get_show_hydrogens, _set_show_hydrogens)


  # charge
  def _get_charge( self):
    return self.__charge

  def _set_charge( self, charge):
    self.__charge = charge
    self.dirty = 1

  charge = property( _get_charge, _set_charge)



  # pos
  def _get_pos( self):
    return self.__pos

  def _set_pos( self, pos):
    self.__pos = pos
    self.dirty = 1

  pos = property( _get_pos, _set_pos)



  # valency
  def _get_valency( self):
    try:
      self.__valency
    except AttributeError:
      self.set_valency_from_name()
    return self.__valency

  def _set_valency( self, val):
    self.__valency = val

  valency = property( _get_valency, _set_valency, None, "atoms (maximum) valency, used for hydrogen counting")



  # xml_text (override of text_like.xml_text)
  def _get_xml_text( self):
    return self.get_ftext()

  def _set_xml_text( self, xml_text):
    pass
    #self.set_name( xml_text)  -- ignored for now

  xml_text = property( _get_xml_text, _set_xml_text)



  # font_size (override of text_like.xml_text)
  def _get_font_size( self):
    return self.__font_size

  def _set_font_size( self, font_size):
    self.__font_size = font_size
    self.dirty = 1
    self.__reposition_on_redraw = 1

  font_size = property( _get_font_size, _set_font_size)



  # parent
  def _get_parent( self):
    return self.molecule

  def _set_parent( self, par):
    self.molecule = par

  parent = property( _get_parent, _set_parent, None,
                     "returns self.molecule")



  # multiplicity
  def _get_multiplicity( self):
    return self.__multiplicity
  
  def _set_multiplicity( self, multiplicity):
    self.__multiplicity = multiplicity

  multiplicity = property( _get_multiplicity, _set_multiplicity, None,
                           "returns multiplicity of molecule")


  # drawn
  def _get_drawn( self):
    """is the atoms drawn on the paper or just virtual"""
    if hasattr( self, 'item') and self.item:
      return 1
    return 0

  drawn = property( _get_drawn, None, None, "tells if the atom is already drawn")






  ## // -------------------- END OF PROPERTIES --------------------------

  def copy_settings( self, other):
    """copies settings of self to other, does not check if other is capable of receiving it"""
    meta_enabled.copy_settings( self, other)
    area_colored.copy_settings( self, other)
    point_drawable.copy_settings( self, other)
    text_like.copy_settings( self, other)
    child_with_paper.copy_settings( self, other)
    other.pos = self.pos




  def set_name( self, name, interpret=1, check_valency=1, occupied_valency=None):
    ret = self._set_name( name, interpret=interpret, check_valency=check_valency, occupied_valency=occupied_valency)
    self.set_valency_from_name()
    return ret


  def _set_name( self, name, interpret=1, check_valency=1, occupied_valency=None):
    # every time name is set the charge should be set to zero or the value specified by marks
    self.charge = self.get_charge_from_marks()
    self.dirty = 1
    # try to interpret name
    if name.lower() != 'c':
      self.show = 1
    else:
      self.show = 0
    elch = self.split_element_and_charge( name)
    if elch:
      # name is element symbol + charge
      self.name = elch[0]
      self.show_hydrogens = 0
      self.charge += elch[1]
      return True
    else:
      # try if name is hydrogenated form of an element
      form = PT.text_to_hydrogenated_atom( name)
      if form:
        # it is!
        a = form.keys()
        a.remove( 'H')
        if occupied_valency == None:
          valency = self.get_occupied_valency()
        else:
          valency = occupied_valency
        if form['H'] in [i-valency+self.charge for i in PT.periodic_table[a[0]]['valency']]:
          self.name = a[0]
          self.show_hydrogens = 1
          #self.show = 1
          return True
    return False





  def get_text( self):
    if not self.show:
      return self.name
    elif self.show:
      ret = self.name
      # hydrogens
      if self.show_hydrogens:
        v = self.free_valency
        if v:
          h = 'H'
        else:
          h = ''
        if v > 1:
          h += '%d' % v
        if self.pos == 'center-last':
          ret = h + ret
        else:
          ret = ret + h
      # charge
      if self.charge:
        ch = ''
        if abs( self.charge) > 1:
          ch += str( abs( self.charge - self.get_charge_from_marks()))
        if self.charge -self.get_charge_from_marks() > 0:
          ch += '+'
        else:
          ch += '-'
      else:
        ch = ''
      if self.pos == 'center-last':
        return ch + ret
      else:
        return ret + ch




  def get_ftext( self):
    ret = self.name
    # hydrogens
    if self.show_hydrogens:
      v = self.free_valency
      if v:
        h = 'H'
      else:
        h = ''
      if v > 1:
        h += '<sub>%d</sub>' % v
      if self.pos == 'center-last':
        ret = h + ret
      else:
        ret = ret + h
    # charge
    if self.charge -self.get_charge_from_marks():
      ch = ''
      if abs( self.charge) > 1:
        ch += str( abs( self.charge -self.get_charge_from_marks()))
      if self.charge -self.get_charge_from_marks() > 0:
        ch = '<sup>%s+</sup>' % ch
      else:
        ch = u'<sup>%s-</sup>' % ch
    else:
      ch = ''
    if self.pos == 'center-last':
      ret = ch + ret
    else:
      ret = ret + ch
    return ret.encode('utf-8')







  def decide_pos( self):
    as = self.get_neighbors()
    p = 0
    for a in as:
      if a.x < self.x:
        p -= 1
      elif a.x > self.x:
        p += 1
    if p > 0:
      self.pos = 'center-last'
    else:
      self.pos = 'center-first'




  def draw( self, redraw=False):
    "draws atom with respect to its properties"
    if self.item:
      warn( "drawing atom that is probably drawn", UserWarning, 2)
    x, y = self.x, self.y
    if self.show:
      self.update_font()
      if not self.pos:
        self.decide_pos()
      # we use self.text to force undo when it is changed (e.g. when atom is added to OH so it changes to O)
      self.text = self.get_ftext()
      name = '<ftext>%s</ftext>' % self.text
      self.ftext = ftext( self.paper, (self.x, self.y), name, font=self.font, pos=self.pos, fill=self.line_color)
      x1, y1, x2, y2 = self.ftext.draw()
      self.item = self.paper.create_rectangle( x1, y1, x2, y2, fill='', outline='', tags=('atom'))
      ## shrink the selector to improve appearance (y2-2)
      self.selector = self.paper.create_rectangle( x1, y1, x2, y2-3, fill=self.area_color, outline='',tags='helper_a')
      self.ftext.lift()
      self.paper.lift( self.item)
    else:
      self.item = self.paper.create_line( x, y, x, y, tags=("atom", 'nonSVG'), fill='')
      self.selector = None
    if not redraw:
      [m.draw() for m in self.marks]
    self.paper.register_id( self.item, self)
    # 
    self.__reposition_on_redraw = 0



  def redraw( self, suppress_reposition=0):
    if self.__reposition_on_redraw and not suppress_reposition:
      self.reposition_marks()
      self.__reposition_on_redraw = 0
    self.update_font()
    # at first we delete everything...
    self.paper.unregister_id( self.item)
    self.paper.delete( self.item)
    if self.selector:
      self.paper.delete( self. selector)
    if self.ftext:
      self.ftext.delete()
    self.item = None # to ensure that warning in draw() is not triggered when redrawing
    # ...then we draw it again
    self.draw( redraw=True)
    [m.redraw() for m in self.marks]

    if self._selected:
      self.select()
    else:
      self.unselect()
    if not self.dirty:
      pass
      #print "redrawing non-dirty atom"
    self.dirty = 0

      



  def focus( self):
    if self.show:
      self.paper.itemconfig( self.selector, fill='grey')
    else:
      x, y = self.x, self.y
      self.focus_item = self.paper.create_oval( x-4, y-4, x+4, y+4, tags='helper_f')
      self.paper.lift( self.item)




  def unfocus( self):
    if self.show:
      self.paper.itemconfig( self.selector, fill=self.area_color)
    if self.focus_item:
      self.paper.delete( self.focus_item)
      self.focus_item = None




  def select( self):
    if self.show:
      self.paper.itemconfig( self.selector, outline='black')
    else:
      x, y = self.x, self.y
      if self.selector:
        self.paper.coords( self.selector, x-2, y-2, x+2, y+2)
      else:
        self.selector = self.paper.create_rectangle( x-2, y-2, x+2, y+2)
      self.paper.lower( self.selector)
    self._selected = 1




  def unselect( self):
    if self.show:
      self.paper.itemconfig( self.selector, outline='')
      #self.paper.lower( self.selector)
    else:
      self.paper.delete( self.selector)
      self.selector = None
    self._selected = 0




  def move( self, dx, dy, dont_move_marks=0):
    """moves object with his selector (when present)"""
    # saving old dirty value
    # d = self.dirty
    self.x += dx
    self.y += dy
    if self.drawn:
      self.paper.move( self.item, dx, dy)
      if self.selector:
        self.paper.move( self.selector, dx, dy)
      if self.ftext:
        self.ftext.move( dx, dy)
      if not dont_move_marks:
        for m in self.marks:
          m.move( dx, dy)
    # restoring dirty value because move does not dirty the atom
    # self.dirty = d



  def move_to( self, x, y, dont_move_marks=0):
    dx = x - self.x
    dy = y - self.y
    self.move( dx, dy, dont_move_marks=dont_move_marks)





  def get_xy( self):
    return self.x, self.y




  def get_xyz( self, real=0):
    """returns atoms coordinates, default are screen coordinates, real!=0
    changes it to real coordinates (these two are usually different for imported molecules)"""
    if real:
      x, y = self.paper.screen_to_real_coords( (self.x, self.y))
      z = self.z *self.paper.screen_to_real_ratio()
      return x, y, z
    else:
      return self.x, self.y, self.z





  def delete( self):
    for m in self.marks:
      m.delete()
    if self.focus_item:
      self.unfocus()
    if self.selector:
      self.unselect()
      if self.show:
        self.paper.delete( self.selector)
        self.selector = None
        self._selected = 0
    if self.item:
      self.paper.unregister_id( self.item)
      self.paper.delete( self.item)
      self.item = None
    if self.ftext:
      self.ftext.delete()
    return self




  def read_package( self, package):
    """reads the dom element package and sets internal state according to it"""
    a = ['no','yes']
    on_off = ['off','on']
    self.id = package.getAttribute( 'id')
    # marks (we read them here because they influence the charge)
    for m in package.getElementsByTagName( 'mark'):
      mrk = marks.mark.read_package( m, self)
      self.marks.add( mrk)
    self.pos = package.getAttribute( 'pos')
    position = package.getElementsByTagName( 'point')[0]
    # reading of coords regardless of their unit
    x, y, z = Screen.read_xml_point( position)
    if z != None:
      self.z = z* self.paper.real_to_screen_ratio()
    # needed to support transparent handling of molecular size
    x, y = self.paper.real_to_screen_coords( (x, y))
    self.x = x
    self.y = y
    ft = package.getElementsByTagName('ftext')
    if ft:
      self.set_name( reduce( operator.add, [e.toxml() for e in ft[0].childNodes], '').encode('utf-8'), check_valency=0, interpret=0)
    else:
      self.set_name( package.getAttribute( 'name'), check_valency=0)
    # charge
    self.charge = package.getAttribute('charge') and int( package.getAttribute('charge')) or 0
    # hydrogens
    if package.getAttribute( 'hydrogens'):
      self.show_hydrogens = package.getAttribute('hydrogens')
    else:
      self.show_hydrogens = 0
    # font and fill color
    fnt = package.getElementsByTagName('font')
    if fnt:
      fnt = fnt[0]
      self.font_size = int( fnt.getAttribute( 'size'))
      self.font_family = fnt.getAttribute( 'family')
      if fnt.getAttribute( 'color'):
        self.line_color = fnt.getAttribute( 'color')
    # show
    if package.getAttribute( 'show'):
      self.show = package.getAttribute( 'show')
    else:
      self.show = (self.name!='C')
    # background color
    if package.getAttributeNode( 'background-color'):
      self.area_color = package.getAttribute( 'background-color')
    # multiplicity
    if package.getAttribute( 'multiplicity'):
      self.multiplicity = int( package.getAttribute( 'multiplicity'))
    # valency
    if package.getAttribute( 'valency'):
      self.valency = int( package.getAttribute( 'valency'))
    # number
    if package.getAttribute( 'show_number'):
      self.show_number = bool( data.booleans.index( package.getAttribute( 'show_number')))
    if package.getAttribute( 'number'):
      self.number = package.getAttribute( 'number')
    # free_sites
    if package.getAttribute( 'free_sites'):
      self.free_sites = int( package.getAttribute( 'free_sites'))



  def get_package( self, doc):
    """returns a DOM element describing the object in CDML,
    doc is the parent document which is used for element creation
    (the returned element is not inserted into the document)"""
    yes_no = ['no','yes']
    on_off = ['off','on']
    a = doc.createElement('atom')
    a.setAttribute( 'id', str( self.id))
    # charge
    if self.charge:
      a.setAttribute( "charge", str( self.charge))
    #show attribute is set only when non default
    if (self.show and self.name=='C') or (not self.show and self.name!='C'): 
      a.setAttribute('show', yes_no[ self.show])
    if self.show:
      a.setAttribute( 'pos', self.pos)
    if self.font_size != self.paper.standard.font_size \
       or self.font_family != self.paper.standard.font_family \
       or self.line_color != self.paper.standard.line_color:
      font = dom_extensions.elementUnder( a, 'font', attributes=(('size', str( self.font_size)), ('family', self.font_family)))
      if self.line_color != self.paper.standard.line_color:
        font.setAttribute( 'color', self.line_color)
    a.setAttribute( 'name', self.name)
    if self.show_hydrogens:
      a.setAttribute('hydrogens', on_off[self.show_hydrogens])
    if self.area_color != self.paper.standard.area_color:
      a.setAttribute( 'background-color', self.area_color)
    # needed to support transparent handling of molecular size
    x, y, z = map( Screen.px_to_text_with_unit, self.get_xyz( real=1))
    if self.z:
      dom_extensions.elementUnder( a, 'point', attributes=(('x', x), ('y', y), ('z', z)))
    else: 
      dom_extensions.elementUnder( a, 'point', attributes=(('x', x), ('y', y)))
    # marks
    for o in self.marks:
      a.appendChild( o.get_package( doc))
    # multiplicity
    if self.multiplicity != 1:
      a.setAttribute( 'multiplicity', str( self.multiplicity))
    # valency
    a.setAttribute( 'valency', str( self.valency))
    # number
    if self.number:
      a.setAttribute( 'number', self.number)
      a.setAttribute( 'show_number', data.booleans[ int( self.show_number)])
    # free_sites
    if self.free_sites:
      a.setAttribute( 'free_sites', self.free_sites)
    return a





  def toggle_center( self, mode = 0):
    """toggles the centering of text between 'center-first' and 'center-last'(mode=0)
    or sets it strictly - mode=-1, mode=1"""
    if not mode:
      if self.pos == 'center-last':
        self.pos = 'center-first'
      else:
        self.pos = 'center-last'
    elif mode == -1:
      self.pos = 'center-first'
    else:
      self.pos = 'center-last'
    self.redraw()




  def update_font( self):
    self.font = tkFont.Font( family=self.font_family, size=self.font_size)
        



  def scale_font( self, ratio):
    """scales font of atom. does not redraw !!"""
    self.font_size = int( round( self.font_size * ratio))
    self.update_font()






  def get_formula_dict( self):
    """returns formula as dictionary that can
    be passed to functions in periodic_table"""
    ret = PT.formula_dict( self.name)
    if self.free_valency > 0:
      ret['H'] = self.free_valency
    return ret





  ##LOOK
  def atoms_bound_to( self):
    return self.get_neighbors()




  def lift( self):
    # marks
    [m.lift() for m in self.marks]
    if self.ftext:
      self.ftext.lift()
    if self.item:
      self.paper.lift( self.item)


  def lift_selector( self):
    if self.selector:
      self.paper.lift( self.selector)




  # overrides parents.vertex_common method
  def _set_mark_helper( self, mark, sign=1):
    if mark == 'plus':
      self.charge += 1*sign
    elif mark == 'minus':
      self.charge -= 1*sign
    elif mark == "radical":
      self.multiplicity += 1*sign
    elif mark == "biradical":
      self.multiplicity += 2*sign

    



  def transform( self, tr):
    x, y = tr.transform_xy( self.x, self.y)
    self.move_to( x, y, dont_move_marks=1)
    for m in self.marks:
      m.transform( tr)




  def update_after_valency_change( self):
    if self.free_valency <= 0:
      self.raise_valency_to_senseful_value()
    if self.show_hydrogens:
      self.redraw()




  def __str__( self):
    return self.id



  def get_charge_from_marks( self):
    res = 0
    for m in self.marks:
      if m.__class__.__name__ == 'plus':
        res += 1
      elif m.__class__.__name__ == "minus":
        res -= 1
    return res





  def generate_marks_from_cheminfo( self):
    if self.charge == 1 and not self.get_marks_by_type( 'plus'):
      self.create_mark( 'plus', draw=0)
    elif self.charge == -1 and not self.get_marks_by_type( 'minus'):
      self.create_mark( 'minus', draw=0)
    if self.multiplicity == 2 and not self.get_marks_by_type( 'radical'):
      self.create_mark( 'radical', draw=0)
    elif self.multiplicity == 3 and not (self.get_marks_by_type( 'biradical') or len( self.get_marks_by_type( 'radical')) == 2):
      self.create_mark( 'biradical', draw=0)
  



  ##LOOK
  def get_occupied_valency( self):
    return self.occupied_valency



  def set_valency_from_name( self):
    for val in PT.periodic_table[ self.name]['valency']:
      self.valency = val
      try:
        fv = self.free_valency
      except:
        return  # this happens on read
      if fv >= 0:
        return

    

  def bbox( self):
    """returns the bounding box of the object as a list of [x1,y1,x2,y2]"""
    if self.item:
      return self.paper.bbox( self.item)
    else:
      # we have to calculate it, the atoms was not drawn yet
      if self.show:
        length = self.font.measure( self.get_text())
        if self.pos == 'center-first':
          dx = self.font.measure( self.get_text()[0]) / 2
          return (self.x + length - dx, self.y + 0.3*self.font_size, self.x - dx, self.y - 0.7*self.font_size) 
        else:
          dx = self.font.measure( self.get_text()[-1]) / 2
          return (self.x + dx, self.y + 0.3*self.font_size, self.x - length + dx, self.y - 0.7*self.font_size) 
      else:
        return self.x, self.y, self.x, self.y


  ##LOOK  (make static)
  def split_element_and_charge( self, txt):
    """returns tuple of (element, charge) or None if the text does not match this pattern"""
    ### this could be a static method
    splitter = re.compile("^([a-z]+)([0-9]*)([+-]?)$")
    match = splitter.match( txt.lower())
    if match:
      if match.group(1).capitalize() not in PT.periodic_table:
        return None
      if match.group(3) == '+':
        charge = match.group(2) and int( match.group(2)) or 1
      elif match.group(3) == '-':
        charge = match.group(2) and -int( match.group(2)) or -1
      else:
        charge = 0
      return (match.group(1).capitalize(), charge)
    else:
      return None



