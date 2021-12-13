from pelican import signals
from pelican.contents import Content
from pelican.readers import BaseReader
from pelican.generators import Generator
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
            'status': message.get('status', 'hidden')
        }

        # Slug is important because it Pelican's slugification affects
        # the final URL, and we care about exact URLs here.
        # So for redirect files, we assume that you named them carefully.
        # And allow overriding by explicit slug.
        slug = message.get('slug')
        if not slug:
            slug = os.path.splitext(os.path.basename(source_path))[0]
        if slug:
            metadata['slug'] = slug

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
        # XXX ... or no; 'foo'.endswith(('a', 'x', 'o')) -> True
        for extension in RedirectReader.file_extensions:
            redirect_input_files.update(
                self.get_files(paths=input_paths, extensions=extension)
            )

        redirects = []

        # By the time this runs, the default generators have already
        # run and created Page instances for all .302 files,
        # and those have correct url path calculations.
        # We iterate over all of those, and steal the correct paths.
        # Dirty hack :)
        source_path_to_final_path = {}
        for type_key in ('pages', 'articles'):
            content_records = self.context.get(type_key)
            for cr in content_records or []:
                # Get all redirects seen so far.
                if cr.reader == 'redirect':
                    source_path_to_final_path[cr.source_path] = cr.save_as

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

            if redirect.source_path in source_path_to_final_path:
                redirect.override_save_as = source_path_to_final_path[
                    redirect.source_path]

            self.add_source_path(redirect)
            redirects.append(redirect)

        # print "Got a buncha redirects: %s" % redirects
        self.context['redirects'] = redirects

    def generate_output(self, writer):
        for source in self.context['redirects']:
            dest = source.save_as
            template = self.get_template('redirect')

            # We need to override the file because I haven't found a way
            # to prevent the Page / Article generators from writing the
            # .302 article as a normal (empty) Page before we get here.
            # You can do that by directory (via ARTICLE_EXCLUDES) but not
            # by file extension, apparently.
            # So this hack prevents an error if the file is already
            # marked as overridden.
            #
            # ... Unfortunately, dest doesn't match the path of Pages
            # nested in subdirs. So this goes in the wrong place
            # and the Page is still there in the wrong place.
            # Where/ how do they handle subdirs?
            try:
                _path = os.path.join(writer.output_path, dest)
                writer._overridden_files.remove(_path)
                #print "Removed redirect file at %s" % _path
            except KeyError:
                #print "Redirect not in overridden files at %s" % _path
                pass

            writer.write_file(
                dest, template, self.context,
                page=source,
                relative_urls=self.settings['RELATIVE_URLS'],
                override_output=True)

    def generate_feeds(self):
        """
        Redirects don't go in any feeds.
        """
        # print "EMPTY REDIRECT FEED for %s" % self
        return

    def generate_period_archives(self):
        """
        Redirects don't go in any archives.  (I think.)
        """
        return


def add_reader(readers):
    for ext in RedirectReader.file_extensions:
        readers.reader_classes[ext] = RedirectReader


def get_generators(pelican_object):
    # define a new generator here if you need to
    return RedirectGenerator


def register():
    signals.readers_init.connect(add_reader)
    signals.get_generators.connect(get_generators)
