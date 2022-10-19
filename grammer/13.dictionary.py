print("\n*************************************ex1*************************************")
# Dictionary는 "키(Key) - 값(Value)" 쌍을 요소로 갖는 컬렉션이다
company = {"삼성전자": '005930', "LG전자": '066570'}

print(f"company: {company} , type: {type(company)}")
# 특정 key값의 value 출력
print("삼성전자 : ", company["삼성전자"])

# key, value 추가
company["SK텔레콤"] = '017670'
print(f"company: {company} , type: {type(company)}")


print("\n*************************************ex2*************************************")
# for문에 활용
for key in company:
    val = company[key]
    print(f"key : {key}, val : {val}")


print("\n*************************************ex3*************************************")
# key 값 가져오기
keys = company.keys()
for k in keys:
    print(k)

# values 값 가져오기
values = company.values()
for v in values:
    print(v)


print("\n*************************************ex4*************************************")
# dict의 items()는 Dictonary의 키(key)-값(value) 쌍 Tuple 들로 구성된 dict_items 객체를 리턴
items = company.items()
print(f"items : {items}")

for k, v in company.items():
    print(f"key : {k}, value : {v}")

print("\n*************************************ex5*************************************")
# defaultdict()는 딕셔너리를 만드는 dict클래스의 서브클래스

from collections import defaultdict

# defaultdict int
dict_int = defaultdict(int)
# A 라는 key 추가, 이 때 값을 할당하지 않으면 디폴트 값이 0이 된다.
dict_int['A']
print(f"dict_int['A'] :{dict_int['A']}, Type : {type(dict_int['A'])}")
# B 라는 key 추가, [1, 2, 3] 이라는 리스트 값
dict_int['B'] = 1
print(f"dict_int['B'] :{dict_int['B']}, Type : {type(dict_int['B'])}")


print("\n*************************************ex6*************************************")
# defaultdict list
dict_list = defaultdict(list)
# A 라는 key 추가, 이 때 값을 할당하지 않으면 디폴트 값이 빈 list가 된다.
dict_list['A']
print(f"dict_list['A'] :{dict_list['A']}, Type : {type(dict_list['A'])}")
# B 라는 key 추가, [1, 2, 3] 이라는 리스트 값
dict_list['B'] = [1, 2, 3]
print(f"dict_list['B'] :{dict_list['B']}, Type : {type(dict_list['B'])}")


print("\n*************************************ex7*************************************")
# dictionary -> dataframe 변환
from pandas import DataFrame
dict_list2 = defaultdict(list)
dict_list2["종목명"] = ['삼성전자', 'LG전자', 'SK텔레콤']
dict_list2["종목코드"] = ['005930', '066570', '017670']

df = DataFrame.from_dict(dict_list2)
print(f"df : {df} , type : {type(df)}")