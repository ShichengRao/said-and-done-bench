from pipeline import transform

def test_no_documents():
    result=transform({'documents':[],'membership':[],'queries':[{'id':'q','tenant':'t','user':'u','at':0,'terms':[]}]})
    assert result=={'queries':[{'id':'q','groups':[],'visible':[],'hits':[]}],'blocker_codes':[]}
