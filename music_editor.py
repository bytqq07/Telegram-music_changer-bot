import logging
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.wave import WAVE
from mutagen.aiff import AIFF
from mutagen.mp4 import MP4
from PIL import Image
import io

logger = logging.getLogger(__name__)


class MusicEditor:
    def __init__(self, temp_dir: Path):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)

    def read_metadata(self, file_path: str) -> dict:
        """Read metadata from audio file"""
        try:
            file_path = Path(file_path)
            suffix = file_path.suffix.lower()

            metadata = {
                'title': 'Unknown',
                'artist': 'Unknown',
                'album': 'Unknown',
                'format': suffix
            }

            try:
                # Try ID3 tags (MP3)
                if suffix in ['.mp3']:
                    audio = EasyID3(str(file_path))
                    metadata['title'] = audio.get('title', ['Unknown'])[0]
                    metadata['artist'] = audio.get('artist', ['Unknown'])[0]
                    metadata['album'] = audio.get('album', ['Unknown'])[0]

                # FLAC
                elif suffix in ['.flac']:
                    audio = FLAC(str(file_path))
                    metadata['title'] = audio.get('title', ['Unknown'])[0]
                    metadata['artist'] = audio.get('artist', ['Unknown'])[0]
                    metadata['album'] = audio.get('album', ['Unknown'])[0]

                # OGG Vorbis
                elif suffix in ['.ogg', '.oga']:
                    audio = OggVorbis(str(file_path))
                    metadata['title'] = audio.get('title', ['Unknown'])[0]
                    metadata['artist'] = audio.get('artist', ['Unknown'])[0]
                    metadata['album'] = audio.get('album', ['Unknown'])[0]

                # OGG Opus
                elif suffix in ['.opus']:
                    audio = OggOpus(str(file_path))
                    metadata['title'] = audio.get('title', ['Unknown'])[0]
                    metadata['artist'] = audio.get('artist', ['Unknown'])[0]
                    metadata['album'] = audio.get('album', ['Unknown'])[0]

                # MP4 (M4A, AAC)
                elif suffix in ['.m4a', '.aac', '.mp4']:
                    audio = MP4(str(file_path))
                    metadata['title'] = audio.get('\xa9nam', ['Unknown'])[0] if isinstance(audio.get('\xa9nam', ['Unknown'])[0], str) else str(audio.get('\xa9nam', ['Unknown'])[0])
                    metadata['artist'] = audio.get('\xa9ART', ['Unknown'])[0] if isinstance(audio.get('\xa9ART', ['Unknown'])[0], str) else str(audio.get('\xa9ART', ['Unknown'])[0])
                    metadata['album'] = audio.get('\xa9alb', ['Unknown'])[0] if isinstance(audio.get('\xa9alb', ['Unknown'])[0], str) else str(audio.get('\xa9alb', ['Unknown'])[0])

                # WAVE
                elif suffix in ['.wav', '.wave']:
                    audio = WAVE(str(file_path))
                    if audio.tags:
                        metadata['title'] = audio.get('title', ['Unknown'])[0]
                        metadata['artist'] = audio.get('artist', ['Unknown'])[0]

                # AIFF
                elif suffix in ['.aiff', '.aif']:
                    audio = AIFF(str(file_path))
                    if audio.tags:
                        metadata['title'] = audio.get('title', ['Unknown'])[0]
                        metadata['artist'] = audio.get('artist', ['Unknown'])[0]

            except Exception as e:
                logger.warning(f"Could not read full metadata: {e}")

            return metadata

        except Exception as e:
            logger.error(f"Error reading metadata: {e}")
            return {'title': 'Unknown', 'artist': 'Unknown', 'album': 'Unknown', 'format': 'Unknown'}

    def edit_metadata(self, file_path: str, title: str = None, artist: str = None,
                     album: str = None, cover_path: str = None) -> str:
        """Edit metadata in audio file and return path to modified file"""
        try:
            file_path = Path(file_path)
            suffix = file_path.suffix.lower()

            # Create output path
            output_path = self.temp_dir / f"modified_{file_path.name}"

            # Copy original file to output
            import shutil
            shutil.copy2(str(file_path), str(output_path))

            try:
                if suffix in ['.mp3']:
                    self._edit_id3(str(output_path), title, artist, album, cover_path)

                elif suffix in ['.flac']:
                    self._edit_flac(str(output_path), title, artist, album, cover_path)

                elif suffix in ['.ogg', '.oga']:
                    self._edit_ogg_vorbis(str(output_path), title, artist, album, cover_path)

                elif suffix in ['.opus']:
                    self._edit_ogg_opus(str(output_path), title, artist, album, cover_path)

                elif suffix in ['.m4a', '.aac', '.mp4']:
                    self._edit_mp4(str(output_path), title, artist, album, cover_path)

                elif suffix in ['.wav', '.wave']:
                    self._edit_wave(str(output_path), title, artist, album, cover_path)

                elif suffix in ['.aiff', '.aif']:
                    self._edit_aiff(str(output_path), title, artist, album, cover_path)

            except Exception as e:
                logger.warning(f"Could not write all metadata: {e}")

            logger.info(f"File modified: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Error editing metadata: {e}")
            raise

    def _edit_id3(self, file_path: str, title: str = None, artist: str = None,
                  album: str = None, cover_path: str = None):
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
        try:
            audio = ID3(file_path)
        except ID3NoHeaderError:
            audio = ID3()
        if title:
            audio['TIT2'] = TIT2(encoding=3, text=title)
        if artist:
            audio['TPE1'] = TPE1(encoding=3, text=artist)
        if album:
            audio['TALB'] = TALB(encoding=3, text=album)
        if cover_path:
            from PIL import Image
            import io
            # Re-encode to guarantee valid JPEG bytes
            img = Image.open(cover_path).convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=95)
            cover_data = buf.getvalue()
            audio['APIC:'] = APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=cover_data
            )
        audio.save(file_path, v2_version=4)

    def _edit_flac(self, file_path: str, title: str = None, artist: str = None,
                   album: str = None, cover_path: str = None):
        audio = FLAC(file_path)
        if title:
            audio['title'] = [title]
        if artist:
            audio['artist'] = [artist]
        if album:
            audio['album'] = [album]
        if cover_path:
            self._add_flac_cover(audio, cover_path)
        audio.save()

    def _add_flac_cover(self, audio, cover_path: str):
        """Add cover art to FLAC"""
        from mutagen.flac import Picture

        picture = Picture()
        picture.type = 3  # Cover front

        with open(cover_path, 'rb') as img:
            picture.data = img.read()

        picture.mime = 'image/jpeg'
        picture.description = 'Cover'

        # Resize image if needed
        try:
            img = Image.open(cover_path)
            if img.size[0] > 1024 or img.size[1] > 1024:
                img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=90)
                picture.data = buffer.getvalue()
        except:
            pass

        audio.clear_pictures()
        audio.add_picture(picture)

    def _edit_ogg_vorbis(self, file_path: str, title: str = None, artist: str = None,
                        album: str = None, cover_path: str = None):
        """Edit OGG Vorbis metadata"""
        audio = OggVorbis(file_path)

        if title:
            audio['title'] = [title]
        if artist:
            audio['artist'] = [artist]
        if album:
            audio['album'] = [album]

        audio.save()

    def _edit_ogg_opus(self, file_path: str, title: str = None, artist: str = None,
                      album: str = None, cover_path: str = None):
        """Edit OGG Opus metadata"""
        audio = OggOpus(file_path)

        if title:
            audio['title'] = [title]
        if artist:
            audio['artist'] = [artist]
        if album:
            audio['album'] = [album]

        audio.save()

    def _edit_mp4(self, file_path: str, title: str = None, artist: str = None,
                 album: str = None, cover_path: str = None):
        """Edit MP4 metadata (M4A, AAC)"""
        audio = MP4(file_path)

        if title:
            audio['\xa9nam'] = [title]
        if artist:
            audio['\xa9ART'] = [artist]
        if album:
            audio['\xa9alb'] = [album]

        # Add cover art
        if cover_path:
            from mutagen.mp4 import MP4Cover
            from PIL import Image
            import io
            img = Image.open(cover_path).convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=95)
            audio['covr'] = [MP4Cover(buf.getvalue(), imageformat=MP4Cover.FORMAT_JPEG)]

        audio.save()

    def _edit_wave(self, file_path: str, title: str = None, artist: str = None,
                  album: str = None, cover_path: str = None):
        """Edit WAVE metadata"""
        from mutagen.id3 import ID3
        try:
            audio = WAVE(file_path)
            if audio.tags is None:
                from mutagen.id3 import ID3
                audio.add_tags()
        except:
            audio = WAVE()

        if title:
            audio['title'] = [title]
        if artist:
            audio['artist'] = [artist]
        if album:
            audio['album'] = [album]

        audio.save()

    def _edit_aiff(self, file_path: str, title: str = None, artist: str = None,
                  album: str = None, cover_path: str = None):
        """Edit AIFF metadata"""
        try:
            audio = AIFF(file_path)
            if audio.tags is None:
                audio.add_tags()
        except:
            audio = AIFF()

        if title:
            audio['title'] = [title]
        if artist:
            audio['artist'] = [artist]
        if album:
            audio['album'] = [album]

        audio.save()
