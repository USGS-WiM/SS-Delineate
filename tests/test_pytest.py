import delineate # The code to test

def test1():
    #local watershed test in ny
    results = delineate.delineateWatershed(44.00683,-73.74586,'ny','c:/temp/')

    print(results.mergedCatchment)
    assert False
    # if results.mergedCatchment and results.splitCatchment:
    #     assert True
