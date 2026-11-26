import unittest
from pymax.types.domain.attachments.video import VideoRequest
from pymax.dispatch.mapping import EventResolver
from pymax.protocol import Command, Opcode
from types import SimpleNamespace
from unittest.mock import patch

class CompatibilityTests(unittest.TestCase):
    def test_dynamic_video_cdn_path(self):
        result=VideoRequest.model_validate({'CACHE': True,'/video/a.mpd':['cdn.example.org']})
        self.assertEqual(result.url,'https://cdn.example.org/video/a.mpd')
    def test_standard_video_selects_best_mp4(self):
        result=VideoRequest.model_validate({'CACHE':True,'MP4_360':'https://cdn.example.org/360.mp4','MP4_720':'https://cdn.example.org/720.mp4'})
        self.assertEqual(result.url,'https://cdn.example.org/720.mp4')
    def test_event_command_maps_messages(self):
        frame=SimpleNamespace(cmd=Command.EVENT,opcode=Opcode.NOTIF_MESSAGE,payload={})
        with patch.dict('pymax.dispatch.mapping.EVENT_MAP',{Opcode.NOTIF_MESSAGE:lambda _: 'handled'}):
            self.assertEqual(EventResolver().resolve(frame),'handled')
if __name__=='__main__':unittest.main()
