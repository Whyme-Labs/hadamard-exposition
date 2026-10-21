import unittest
from review_findings import clean_footer, metadata_matches

class ReviewTests(unittest.TestCase):
    def test_preserve_user_text(self):
        footer='<!-- codesmith:footer -->https://backend.blacksmith.sh/track/enable-autofix?signature='+'a'*32+'<!-- /codesmith:footer -->'
        body='User\ntext\n'+footer+'\nTrailing user text\n'
        clean,changed=clean_footer(body)
        self.assertTrue(changed)
        self.assertEqual(clean,'User\ntext\n\nTrailing user text\n')
    def test_unrelated_content_unchanged(self):
        for text in ('ordinary text','https://example.org/?signature=abc','<!-- codesmith:footer -->unsigned<!-- /codesmith:footer -->'):
            self.assertEqual(clean_footer(text),(text,False))
    def test_ambiguous_footers_not_changed(self):
        s='<!-- codesmith:footer -->https://backend.blacksmith.sh/track/enable-autofix?signature=a<!-- /codesmith:footer -->'
        self.assertEqual(clean_footer(s+s),(s+s,False))
    def test_metadata_fields_identified(self):
        value={'author_email':'fixture'+'@gmail.com','description':'path /home/example/file'}
        found=list(metadata_matches(value))
        self.assertEqual({x[1] for x in found},{'.author_email','.description'})

if __name__=='__main__':unittest.main()
