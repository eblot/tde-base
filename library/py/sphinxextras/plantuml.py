# -*- coding: utf-8 -*-
"""
    sphinxcontrib.plantuml
    ~~~~~~~~~~~~~~~~~~~~~~

    Embed PlantUML diagrams on your documentation.

    :copyright: Copyright 2010 by Yuya Nishihara <yuya@tcha.org>.
    :license: BSD, see LICENSE for details.
"""
import errno, os, re, shlex, subprocess, sys
try:
    from hashlib import sha1
except ImportError:  # Python<2.5
    from sha import sha as sha1
from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.errors import SphinxError
from sphinx.util.compat import Directive
from sphinx.util.osutil import ensuredir, ENOENT

class PlantUmlError(SphinxError):
    pass

class plantuml(nodes.General, nodes.Element):
    pass

class UmlDirective(Directive):
    """Directive to insert PlantUML markup

    Example::

        .. uml::
           :alt: Alice and Bob

           Alice -> Bob: Hello
           Alice <- Bob: Hi
    """
    has_content = True
    option_spec = {'alt': directives.unchanged,
                   # TODO: process the following options by html writer
                   'height': directives.length_or_unitless,
                   'width': directives.length_or_percentage_or_unitless,
                   'scale': directives.percentage}

    def run(self):
        node = plantuml(self.block_text, **self.options)
        node['uml'] = '\n'.join(self.content)
        return [node]

def generate_name(self, node, fileformat):
    key = sha1(node['uml'].encode('utf-8')).hexdigest()
    fname = 'plantuml-%s.%s' % (key, fileformat)
    imgpath = getattr(self.builder, 'imgpath', None)
    if imgpath:
        return ('/'.join((self.builder.imgpath, fname)),
                os.path.join(self.builder.outdir, '_images', fname))
    else:
        return fname, os.path.join(self.builder.outdir, fname)

_ARGS_BY_FILEFORMAT = {
    'eps': '-teps'.split(),
    'png': (),
    'svg': '-tsvg'.split(),
    }

def generate_plantuml_args(self, fileformat):
    if isinstance(self.builder.config.plantuml, str):
        args = shlex.split(self.builder.config.plantuml)
    else:
        args = list(self.builder.config.plantuml)
    args.extend('-pipe -charset utf-8'.split())
    args.extend(_ARGS_BY_FILEFORMAT[fileformat])
    return args

def render_remote_plantuml(self, node, fileformat, outfname):
    from base64 import b64encode
    from urllib.parse import urlencode
    from urllib.request import urlopen, Request
    from neo.resources import Resources
    baseurl = Resources().build_url('plantuml', 'plantuml')
    query = urlencode((('format', fileformat),
                       ('uml', b64encode(node['uml'].encode('utf-8')))))
    uri = Request('%s/uml' % baseurl.rstrip('/'), query.encode('utf-8'))
    inf = urlopen(uri)
    with open(outfname, 'wb') as out:
        out.write(inf.read())

def render_plantuml(self, node, fileformat):
    refname, outfname = generate_name(self, node, fileformat)
    if os.path.exists(outfname):
        return refname, outfname  # don't regenerate
    ensuredir(os.path.dirname(outfname))
    if self.builder.config.plantuml_remote:
        render_remote_plantuml(self, node, fileformat, outfname)
        return refname, outfname
    f = open(outfname, 'wb')
    try:
        try:
            p = subprocess.Popen(generate_plantuml_args(self, fileformat),
                                 stdout=f, stdin=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        except OSError as err:
            if err.errno != ENOENT:
                raise
            raise PlantUmlError('plantuml command %r cannot be run'
                                % self.builder.config.plantuml)
        serr = p.communicate(node['uml'].encode('utf-8'))[1]
        if p.returncode != 0:
            raise PlantUmlError('error while running plantuml\n\n' + serr)
        return refname, outfname
    finally:
        f.close()

def _get_png_tag(self, fnames, alt):
    refname, _outfname = fnames['png']
    return ('<img src="%s" alt="plantuml-diagram" class="schema"/>\n'
            % (self.encode(refname)))

def _get_svg_style(fname):
    f = open(fname, mode='rt', encoding='utf-8')
    try:
        for l in f:
            m = re.search(r'<svg\b([^<>]+)', l)
            if m:
                attrs = m.group(1)
                break
        else:
            return
    finally:
        f.close()

    m = re.search(r'\bstyle=[\'"]([^\'"]+)', attrs)
    if not m:
        return
    return m.group(1)

def _get_svg_tag(self, fnames, alt):
    refname, outfname = fnames['svg']
    return '\n'.join([
        # copy width/height style from <svg> tag, so that <object> area
        # has enough space.
        '<object data="%s" type="image/svg+xml" style="%s" class="schema">' % (
            self.encode(refname), _get_svg_style(outfname) or ''),
        _get_png_tag(self, fnames, alt),
        '</object>'])

_KNOWN_HTML_FORMATS = {
    'png': ('png',),
    'svg': ('png', 'svg'),
    }

def html_visit_plantuml(self, node):
    try:
        format = self.builder.config.plantuml_output_format
        uml = node['uml']
        if uml.find('@startditaa') != -1:
            format = 'png'
        try:
            fileformats = _KNOWN_HTML_FORMATS[format]
        except KeyError:
            raise PlantUmlError(
                'plantuml_output_format must be one of %s, but is %r'
                % (', '.join(map(repr, _KNOWN_HTML_FORMATS)), format))
        # fnames: {fileformat: (refname, outfname), ...}
        fnames = dict((e, render_plantuml(self, node, e))
                      for e in fileformats)
    except PlantUmlError as err:
        self.builder.warn(str(err))
        raise nodes.SkipNode
    self.body.append(self.starttag(node, 'p', CLASS='plantuml'))
    gettag = getattr(sys.modules[__name__], '_get_%s_tag' % format)
    self.body.append(gettag(self, fnames, alt=node.get('alt', node['uml'])))
    self.body.append('</p>\n')
    raise nodes.SkipNode

def _convert_eps_to_pdf(self, refname, fname):
    if isinstance(self.builder.config.plantuml_epstopdf, str):
        args = shlex.split(self.builder.config.plantuml_epstopdf)
    else:
        args = list(self.builder.config.plantuml_epstopdf)
    args.append(fname)
    try:
        try:
            p = subprocess.Popen(args, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        except OSError as err:
            # workaround for missing shebang of epstopdf script
            if err.errno != getattr(errno, 'ENOEXEC', 0):
                raise
            p = subprocess.Popen(['bash'] + args, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
    except OSError as err:
        if err.errno != ENOENT:
            raise
        raise PlantUmlError('epstopdf command %r cannot be run'
                            % self.builder.config.plantuml_epstopdf)
    serr = p.communicate()[1]
    if p.returncode != 0:
        raise PlantUmlError('error while running epstopdf\n\n' + serr)
    return refname[:-4] + '.pdf', fname[:-4] + '.pdf'

_KNOWN_LATEX_FORMATS = {
    'eps': ('eps', lambda self, refname, fname: (refname, fname)),
    'pdf': ('eps', _convert_eps_to_pdf),
    'png': ('png', lambda self, refname, fname: (refname, fname)),
    }

def latex_visit_plantuml(self, node):
    try:
        format = self.builder.config.plantuml_latex_output_format
        try:
            fileformat, postproc = _KNOWN_LATEX_FORMATS[format]
        except KeyError:
            raise PlantUmlError(
                'plantuml_latex_output_format must be one of %s, but is %r'
                % (', '.join(map(repr, _KNOWN_LATEX_FORMATS)), format))
        refname, outfname = render_plantuml(self, node, fileformat)
        refname, outfname = postproc(self, refname, outfname)
    except PlantUmlError as err:
        self.builder.warn(str(err))
        raise nodes.SkipNode

    # put node representing rendered image
    img_node = nodes.image(uri=refname, **node.attributes)
    img_node.delattr('uml')
    if not img_node.hasattr('alt'):
        img_node['alt'] = node['uml']
    node.append(img_node)

def latex_depart_plantuml(self, node):
    pass

def pdf_visit_plantuml(self, node):
    try:
        refname, outfname = render_plantuml(self, node, 'eps')
        refname, outfname = _convert_eps_to_pdf(self, refname, outfname)
    except PlantUmlError as err:
        self.builder.warn(str(err))
        raise nodes.SkipNode
    rep = nodes.image(uri=outfname, alt=node.get('alt', node['uml']))
    node.parent.replace(node, rep)

def setup(app):
    app.add_node(plantuml,
                 html=(html_visit_plantuml, None),
                 latex=(latex_visit_plantuml, latex_depart_plantuml))
    app.add_directive('uml', UmlDirective)
    app.add_config_value('plantuml', 'plantuml', 'html')
    app.add_config_value('plantuml_remote', False, 'html')
    app.add_config_value('plantuml_output_format', 'png', 'html')
    app.add_config_value('plantuml_epstopdf', 'epstopdf', '')
    app.add_config_value('plantuml_latex_output_format', 'png', '')

    # imitate what app.add_node() does
    if 'rst2pdf.pdfbuilder' in app.config.extensions:
        from rst2pdf.pdfbuilder import PDFTranslator as translator
        setattr(translator, 'visit_' + plantuml.__name__, pdf_visit_plantuml)
