data=r"\d{1,}\.?\d{0,}(?=\sGB)"
print(data)

list  = []
if list == []:
    print("true")

scores = {'zhangsan':98, 'lisi':89, 'maishu':96}

for name in scores:
  print(f'{name}:{scores[name]}')


list = [{'zhangsan':98, 'lisi':89, 'maishu':96},{'lala':98, 'haha':89, 'maishu':66},{'lala':98, 'haha':89, 'maishu':77}]
list1 = [{'zhangsan':98, 'lisi':89, 'maishu':96}]

missing_num = 2

for count in range(0, min(len(list),missing_num)):
    torrent = list[count]
    print(torrent['maishu'])
