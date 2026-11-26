import contextlib
import importlib.machinery
import importlib.util
import io
import json
import sys
import unittest
from unittest.mock import patch, MagicMock

def load_script(name,path):
    loader=importlib.machinery.SourceFileLoader(name,path)
    spec=importlib.util.spec_from_loader(name,loader)
    mod=importlib.util.module_from_spec(spec);loader.exec_module(mod)
    return mod

class MaxCLITests(unittest.TestCase):
    def setUp(self): self.mod=load_script('maxcli','tools/matrix-max')
    def invoke(self,args):
        conn=MagicMock();response=conn.getresponse.return_value
        response.status=200;response.read.return_value=b'{"partial": true}'
        with patch.object(self.mod,'UnixHTTP',return_value=conn),patch.object(sys,'argv',['matrix-max']+args),contextlib.redirect_stdout(io.StringIO()): self.mod.main()
        return conn.request.call_args.args
    def test_archive_search_routes_and_filters(self):
        method,path=self.invoke(['archive-search','план','--chat','42','--limit','20'])
        self.assertEqual(method,'GET');self.assertIn('/archive/messages?',path)
        self.assertIn('chat=42',path);self.assertIn('limit=20',path)
    def test_index_is_post_and_includes_page_bound(self):
        method,path=self.invoke(['index','--chat','42','--pages','2'])
        self.assertEqual(method,'POST');self.assertIn('/index?',path);self.assertIn('pages=2',path)

class MatrixSearchCLITests(unittest.TestCase):
    def setUp(self): self.mod=load_script('matrixcli','tools/matrix-agent')
    def test_search_uses_matrix_standard_and_room_filter(self):
        with patch.object(self.mod,'call',return_value={'search_categories':{}}) as call:
            self.mod.search('план',room_id='!room:example.org',limit=20)
        method,path,body=call.call_args.args
        self.assertEqual((method,path),('POST','/search'))
        criteria=body['search_categories']['room_events']
        self.assertEqual(criteria['search_term'],'план')
        self.assertEqual(criteria['filter']['rooms'],['!room:example.org'])
        self.assertEqual(criteria['filter']['limit'],20)
    def test_search_rejects_empty_query_and_invalid_limits(self):
        with self.assertRaises(SystemExit):self.mod.search(' ')
        with self.assertRaises(SystemExit):self.mod.search('x',limit=0)

class BulkIndexTests(unittest.TestCase):
    def test_bulk_index_reports_success_and_errors_without_message_contents(self):
        mod=load_script('maxcli_bulk','tools/matrix-max')
        responses=[]
        for status,data in [(200,{'chats':[{'id':1},{'id':2}],'partial':True}),(200,{'indexed':7,'scanned':7,'partial':True}),(503,{'error':'disconnected'})]:
            r=MagicMock();r.status=status;r.read.return_value=json.dumps(data).encode();responses.append(r)
        conn=MagicMock();conn.getresponse.side_effect=responses
        with patch.object(mod.time,'sleep'):
            result=mod.index_all(conn,2,1)
        self.assertEqual(result['chats_succeeded'],1)
        self.assertEqual(result['chats_failed'],1)
        self.assertEqual(result['indexed'],7)
        self.assertTrue(result['partial'])

class PortableCLITests(unittest.TestCase):
    def test_max_socket_can_be_configured(self):
        import os
        with patch.dict(os.environ,{'MATRIX_MAX_SOCKET':'/tmp/custom-max.sock'}):
            mod=load_script('maxcli_portable','tools/matrix-max')
        self.assertEqual(mod.SOCKET,'/tmp/custom-max.sock')
    def test_matrix_server_and_token_file_are_configurable(self):
        import os
        with patch.dict(os.environ,{'MATRIX_HOMESERVER':'https://matrix.example.org','MATRIX_TOKEN_FILE':'/tmp/token'}):
            mod=load_script('matrixcli_portable','tools/matrix-agent')
        self.assertEqual(mod.BASE,'https://matrix.example.org/_matrix/client/v3')
        self.assertEqual(str(mod.TOKEN),'/tmp/token')
    def test_owner_token_file_is_configurable(self):
        import os
        with patch.dict(os.environ,{'MATRIX_OWNER_TOKEN_FILE':'/tmp/owner-token'}):
            mod=load_script('matrixcli_owner','tools/matrix-agent')
        self.assertEqual(str(mod.OWNER_TOKEN),'/tmp/owner-token')
