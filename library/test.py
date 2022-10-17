# def solution(s):
#     answer = 0
#     for size in range(1, len(s)):
#         test = []
#         pos = 0
#         sama = s[pos: pos + size]
#         while pos+size < len(s):
#             w_count = 1
#             pos += 1
#             samb = sama
#
#             while sama == samb:
#                 samb = s[(pos+1) * size: (pos + 2) * size]
#                 w_count += 1
#                 pos += 1
#                 test.append(w_count)
#                 test.append(sama)
#
#             sama = s[pos: pos + size]
#
#             print(pos)
#             print(sama)
#             print(samb)
#             print(test)
#             # try :
#             #     sama = s[pos:pos + size]
#             # except Exception as e:
#             #     print(e)
#             #     aaa
#
#     return answer
#
#
# a = solution("aabbccc")


def solution(rows, columns, connections, queries):
    answer = []

    for qur in queries:
        cutcount = 0
        qy1, qx1, qy2, qx2 = qur
        box = [min(qy1,qy2),min(qx1,qx2), max(qy1,qy2),max(qx1,qx2)]
        allowlist = []
        for qya in range(box[0], box[2]):
            for qxa in range(box[1], box[3]):
                for qyb in range(box[0], box[2]):
                    for qxb in range(box[1], box[3]):
                        allowlist.append([qya, qxa, qyb, qxb])

        # print(box[2], box[0])
        # for qya in range(box[2], box[0]-1, -1):
        #     for qxa in range(box[3], box[0]-1, -1):
        #         for qyb in range(box[2], box[0]-1, -1):
        #             for qxb in range(box[3], box[0]-1, -1):
        #                 allowlist.append([qya, qxa, qyb, qxb])
        # allowlist = [[y1,x1,y2,y2] for  ]
        # allowlist = [[qy1, qx1, qy1, qx2],
        #              [qy1, qx2, qy1, qx1],
        #              [qy2, qx1, qy2, qx2],
        #              [qy2, qx2, qy2, qx1],
        #              [qy1, qx1, qy2, qx2],
        #              [qy1, qx2, qy2, qx1],
        #              [qy2, qx1, qy1, qx2],
        #              [qy2, qx2, qy1, qx1],
        #              [qy1, qx2, qy2, qx2],
        #              [qy2, qx2, qy1, qx2],
        #              [qy1, qx1, qy2, qx1],
        #              [qy2, qx1, qy1, qx1],
        #              ]
        for con in connections:
            cy1, cx1, cy2, cx2 = con
            pos1 = [cy1, cx1]
            pos2 = [cy2, cx2]
            if [qy1, qx1] == pos1 or [qy1, qx1] == pos2:
                cutcount += 1
            elif [qy1, qx2] == pos1 or [qy1, qx2] == pos2:
                cutcount += 1
            elif [qy2, qx1] == pos1 or [qy2, qx1] == pos2:
                cutcount += 1
            elif [qy2, qx2] == pos1 or [qy2, qx2] == pos2:
                cutcount += 1

        for allow in allowlist:

            if allow in connections:
                cutcount -= 1
        cutcount -= 1
        answer.append(cutcount)
        print(cutcount)
    return answer



conections = [[1,1,2,1],[1,2,1,3],[1,3,2,3],[2,2,2,3],[2,2,3,2],[2,3,3,3],[3,2,3,3],[3,2,4,2],[4,1,4,2]]
queries = [[2,2,3,1],[1,2,4,2]]
a = solution(4,3,conections,queries)

apath = "투자주의종목.xels"
apath.grob()