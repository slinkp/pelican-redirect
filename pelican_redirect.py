from pelican import signals
from pelican.contents import Content
from pelican.readers import BaseReader
from pelican.generators import Generator, _FileLoader
from pelican.utils import pelican_open
import email.parser
import logging
import os.path

logger = logging.getLogger(__file__)


class Redirect(Content):
    mandatory_properties = ('location',)
    default_template = 'redirect'


class RedirectReader(BaseReader):
    """
    Reads files ending in .302 and generates an HTML file
    with an appropriate meta-equiv header.
    """

    enabled = True
    file_extensions = ['302']

    def read(self, source_path):
        """
        Parse, and return (content, metadata)
        """
        parser = email.parser.Parser()
        with pelican_open(source_path) as source:
            message = parser.parsestr(source)
        location = message.get('location')
        if not location:
            raise ValueError(
                u"RedirectReader requires a 'location' header in the file")

        delay = float(message.get('delay', 0))

        metadata = {
            'title': message.get('title', u''),
            'location': location,
            'delay': delay,
        }
        content = message.get_payload().strip()
        return content, metadata


class RedirectGenerator(Generator):
    # TODO subclass CachingGenerator

    def generate_context(self):
        redirect_input_files = set()
        input_paths = (
            self.settings['PAGE_PATHS'] + self.settings['ARTICLE_PATHS']
        )
        # TODO there appears to be a pelican bug where get_files()
        # is documented as taking a list of extensions but it actually
        # only takes a string. Report upstream.
        # Hacking around it.
        for extension in RedirectReader.file_extensions:
            redirect_input_files.update(
                self.get_files(paths=input_paths, extensions=extension)
            )

        redirects = []

        for f in redirect_input_files:
            try:
                redirect = self.readers.read_file(
                    base_path=self.path,
                    path=f,
                    content_class=Redirect,
                    context=self.context,
                    # preread_signal=signals.article_generator_preread,
                    preread_sender=self,
                    # context_signal=signals.article_generator_context,
                    context_sender=self)
            except Exception as e:
                logger.error('Could not process redirect %s\n%s', f, e,
                             exc_info=self.settings.get('DEBUG', False))
                self._add_failed_source_path(f)
                continue
            self.add_source_path(redirect)
            redirects.append(redirect)

        print "Got a buncha redirects: %s" % redirects
        self.context['redirects'] = redirects

    def generate_output(self, writer):
        for source in self.context['redirects']:
            dest = source.save_as  # TODO?
            template = self.get_template('redirect')
            rurls = self.settings['RELATIVE_URLS']

            # We need to override the file because I haven't found a way
            # to prevent the Page / Article generators from writing it
            # before we get here.
            # You can do that by directory (via ARTICLE_EXCLUDES) but not
            # by file extension, apparently.
            # So this hack prevents an error if the file is already
            # marked as overridden.

            try:
                writer._overridden_files.remove(
                    os.path.join(writer.output_path, dest))
            except KeyError:
                pass
            import pdb; pdb.set_trace()

            writer.write_file(
                dest, template, self.context, rurls,
                page=source,
                override_output=True)


def add_reader(readers):
    for ext in RedirectReader.file_extensions:
        readers.reader_classes[ext] = RedirectReader


def get_generators(pelican_object):
    # define a new generator here if you need to
    return RedirectGenerator


def register():
    signals.readers_init.connect(add_reader)
    signals.get_generators.connect(get_generators)
