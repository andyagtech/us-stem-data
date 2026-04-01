"""
Name classifier for dissertation author demographics.

Classifies names as Chinese, Indian, Korean, Vietnamese, or other.

Approach:
  - 148 Chinese surnames (pinyin + Wade-Giles/Cantonese romanizations)
  - ~200 Indian surnames covering North/South/Bengali/Gujarati/Punjabi regions
  - Given-name validation using common pinyin/Indian syllables for ambiguous surnames
  - Confidence levels: high / medium
  - Excluded surnames: lee, long, sun (too ambiguous with Western/Korean)

Estimated accuracy (Chinese):
  - True positive rate: ~90-95%
  - False positive rate: ~5-10% (mostly ambiguous surnames)
  - False negative rate: ~5-8% (excluded surnames, rare romanizations)

Estimated accuracy (Indian):
  - True positive rate: ~85-90% (many distinctive surnames)
  - False positive rate: ~3-5% (some overlap with Middle Eastern/European)
  - False negative rate: ~10-15% (South Indian patronymic naming)
"""

# fmt: off
CHINESE_SURNAMES = {
    # Top 100 pinyin surnames
    'wang', 'li', 'zhang', 'liu', 'chen', 'yang', 'zhao', 'huang', 'zhou', 'wu',
    'xu', 'sun', 'hu', 'zhu', 'gao', 'lin', 'he', 'guo', 'ma', 'luo',
    'liang', 'song', 'zheng', 'xie', 'han', 'tang', 'feng', 'yu', 'dong', 'xiao',
    'cheng', 'cao', 'yuan', 'deng', 'fu', 'shen', 'zeng', 'peng', 'lu', 'su',
    'jiang', 'cai', 'jia', 'wei', 'xue', 'ye', 'yan', 'pan', 'du', 'dai',
    'shi', 'ren', 'wan', 'gu', 'qian', 'fan', 'kong', 'zou', 'liao', 'chang',
    'jin', 'tan', 'qiu', 'bai', 'cui', 'wen', 'mao', 'ding', 'tian',
    'qin', 'niu', 'long', 'lei', 'duan', 'hao', 'shao', 'lv',
    # Wade-Giles / Cantonese / alt romanizations
    'wong', 'chan', 'kwong', 'cheung', 'tsai', 'tsang',
    'hsu', 'chiang', 'tung', 'tao', 'chou', 'kuo', 'hou',
    # Added from false-negative review (Section 4)
    'zhong', 'xia', 'xiang', 'meng', 'qiao', 'ge', 'ji', 'pei',
    'yao', 'zhan', 'gong', 'tong', 'rong', 'nie', 'shang', 'bian',
    'weng', 'lou', 'you', 'zuo', 'chai', 'an', 'chi', 'ho',
    'la', 'mi', 'mu', 'pu', 'qi', 'sha', 'shan', 'shui',
    'si', 'suo', 'tie', 'tu', 'wa', 'xi', 'xing', 'xiong',
    'yue', 'zha', 'zhai', 'zhuang', 'zi', 'lan', 'leng',
    'ling', 'mo', 'nai', 'ou', 'bi', 'bo',
    # Additional common ones
    'ke', 'kang', 'min', 'ning', 'ping',
    # Batch 2 — missed common surnames
    'bao', 'qu', 'ai', 'kou', 'sheng', 'fei', 'ruan', 'chu', 'hang',
    'nian', 'nan', 'hua', 'liao', 'kan', 'yin', 'na',
    # Batch 3
    'fang', 'teng', 'lyu', 'lv', 'tao', 'qin', 'wan', 'xiao',
}

# Surnames excluded — too many non-Chinese matches
EXCLUDE_SURNAMES = {'lee', 'long', 'sun'}

# Ambiguous surnames included but flagged for lower confidence
AMBIGUOUS_SURNAMES = {'lin', 'yu', 'jin', 'han', 'he', 'ma', 'fan', 'tang', 'chang',
                      'fu', 'song', 'an', 'chi', 'ho', 'min', 'ping', 'kang'}

# Common Chinese given-name pinyin syllables (for validating ambiguous surnames)
# Expanded to cover all standard Mandarin pinyin initials+finals
PINYIN_SYLLABLES = {
    # A
    'ai', 'an', 'ang', 'ao',
    # B
    'ba', 'bai', 'ban', 'bang', 'bao', 'bei', 'ben', 'beng', 'bi', 'bian',
    'biao', 'bie', 'bin', 'bing', 'bo', 'bu',
    # C
    'cai', 'can', 'cang', 'cao', 'ce', 'cen', 'ceng', 'cha', 'chai', 'chan',
    'chang', 'chao', 'che', 'chen', 'cheng', 'chi', 'chong', 'chou', 'chu',
    'chua', 'chuai', 'chuan', 'chuang', 'chui', 'chun', 'chuo', 'ci', 'cong',
    'cou', 'cu', 'cuan', 'cui', 'cun', 'cuo',
    # D
    'da', 'dai', 'dan', 'dang', 'dao', 'de', 'dei', 'deng', 'di', 'dia',
    'dian', 'diao', 'die', 'ding', 'diu', 'dong', 'dou', 'du', 'duan',
    'dui', 'dun', 'duo',
    # E
    'en', 'er',
    # F
    'fa', 'fan', 'fang', 'fei', 'fen', 'feng', 'fo', 'fou', 'fu',
    # G
    'gai', 'gan', 'gang', 'gao', 'ge', 'gei', 'gen', 'geng', 'gong', 'gou',
    'gu', 'gua', 'guai', 'guan', 'guang', 'gui', 'gun', 'guo',
    # H
    'ha', 'hai', 'han', 'hang', 'hao', 'he', 'hei', 'hen', 'heng', 'hong',
    'hou', 'hu', 'hua', 'huai', 'huan', 'huang', 'hui', 'hun', 'huo',
    # J
    'ji', 'jia', 'jian', 'jiang', 'jiao', 'jie', 'jin', 'jing', 'jiong',
    'jiu', 'ju', 'juan', 'jue', 'jun',
    # K
    'kai', 'kan', 'kang', 'kao', 'ke', 'ken', 'keng', 'kong', 'kou', 'ku',
    'kua', 'kuai', 'kuan', 'kuang', 'kui', 'kun', 'kuo',
    # L
    'la', 'lai', 'lan', 'lang', 'lao', 'le', 'lei', 'leng', 'li', 'lia',
    'lian', 'liang', 'liao', 'lie', 'lin', 'ling', 'liu', 'long', 'lou',
    'lu', 'luan', 'lun', 'luo', 'lv', 'lve',
    # M
    'ma', 'mai', 'man', 'mang', 'mao', 'me', 'mei', 'men', 'meng', 'mi',
    'mian', 'miao', 'mie', 'min', 'ming', 'miu', 'mo', 'mou', 'mu',
    # N
    'na', 'nai', 'nan', 'nang', 'nao', 'ne', 'nei', 'nen', 'neng', 'ni',
    'nian', 'niang', 'niao', 'nie', 'nin', 'ning', 'niu', 'nong', 'nu',
    'nuan', 'nuo', 'nv', 'nve',
    # P
    'pa', 'pai', 'pan', 'pang', 'pao', 'pei', 'pen', 'peng', 'pi', 'pian',
    'piao', 'pie', 'pin', 'ping', 'po', 'pou', 'pu',
    # Q
    'qi', 'qia', 'qian', 'qiang', 'qiao', 'qie', 'qin', 'qing', 'qiong',
    'qiu', 'qu', 'quan', 'que', 'qun',
    # R
    'ran', 'rang', 'rao', 're', 'ren', 'reng', 'ri', 'rong', 'rou', 'ru',
    'rua', 'ruan', 'rui', 'run', 'ruo',
    # S
    'sa', 'sai', 'san', 'sang', 'sao', 'se', 'sen', 'seng', 'sha', 'shai',
    'shan', 'shang', 'shao', 'she', 'shen', 'sheng', 'shi', 'shou', 'shu',
    'shua', 'shuai', 'shuan', 'shuang', 'shui', 'shun', 'shuo', 'si',
    'song', 'sou', 'su', 'suan', 'sui', 'sun', 'suo',
    # T
    'ta', 'tai', 'tan', 'tang', 'tao', 'te', 'teng', 'ti', 'tian', 'tiao',
    'tie', 'ting', 'tong', 'tou', 'tu', 'tuan', 'tui', 'tun', 'tuo',
    # W
    'wa', 'wai', 'wan', 'wang', 'wei', 'wen', 'weng', 'wo', 'wu',
    # X
    'xi', 'xia', 'xian', 'xiang', 'xiao', 'xie', 'xin', 'xing', 'xiong',
    'xiu', 'xu', 'xuan', 'xue', 'xun',
    # Y
    'ya', 'yan', 'yang', 'yao', 'ye', 'yi', 'yin', 'ying', 'yo', 'yong',
    'you', 'yu', 'yuan', 'yue', 'yun',
    # Z
    'za', 'zai', 'zan', 'zang', 'zao', 'ze', 'zei', 'zen', 'zeng', 'zha',
    'zhai', 'zhan', 'zhang', 'zhao', 'zhe', 'zhen', 'zheng', 'zhi', 'zhong',
    'zhou', 'zhu', 'zhua', 'zhuai', 'zhuan', 'zhuang', 'zhui', 'zhun',
    'zhuo', 'zi', 'zong', 'zou', 'zu', 'zuan', 'zui', 'zun', 'zuo',
}

KOREAN_SURNAMES = {
    'kim', 'park', 'choi', 'jung', 'cho', 'kang', 'yoon', 'jang',
    'lim', 'oh', 'shin', 'seo', 'kwon', 'hwang', 'ahn', 'yoo',
    'hong', 'jeon', 'ko', 'moon', 'son', 'bae', 'baek', 'kwak',
    'sung', 'woo', 'ryu', 'nam', 'sim', 'noh', 'ha', 'chung',
    'roh', 'yun', 'byun',
}

VIETNAMESE_SURNAMES = {
    'nguyen', 'tran', 'le', 'pham', 'huynh', 'hoang', 'phan', 'vu', 'vo',
    'dang', 'bui', 'do', 'ho', 'ngo', 'duong', 'ly', 'truong',
    'lam', 'dinh', 'ta', 'luong', 'trinh', 'mai', 'dam',
}

INDIAN_SURNAMES = {
    # ── North Indian / Hindi belt ──
    'sharma', 'gupta', 'verma', 'mishra', 'pandey', 'srivastava', 'tiwari',
    'dubey', 'tripathi', 'yadav', 'shukla', 'bajpai', 'dwivedi', 'upadhyay',
    'trivedi', 'ojha', 'awasthi', 'pathak', 'dixit', 'chaturvedi',
    'sinha', 'prasad', 'thakur', 'chauhan', 'saxena', 'rastogi', 'nigam',
    'agrawal', 'agarwal', 'aggarwal', 'garg', 'goyal', 'mittal', 'bansal',
    'jindal', 'arora', 'singhal', 'khandelwal', 'maheshwari',
    # ── Punjabi / Sikh ──
    'singh', 'kaur', 'gill', 'dhillon', 'sandhu', 'sidhu', 'bajwa',
    'grewal', 'brar', 'virk', 'sahni', 'sethi', 'anand', 'ahuja',
    'bedi', 'walia', 'sodhi', 'oberoi', 'chadha', 'talwar',
    # ── Gujarati / Marathi ──
    'patel', 'shah', 'desai', 'mehta', 'joshi', 'kulkarni', 'deshpande',
    'patil', 'parekh', 'bhatt', 'modi', 'parikh', 'raval', 'trivedi',
    'naik', 'gaikwad', 'jadhav', 'shinde', 'more', 'chavan', 'khare',
    'gokhale', 'sathe', 'karnik', 'jog', 'kelkar', 'phadke', 'apte',
    # ── Bengali ──
    'mukherjee', 'chatterjee', 'banerjee', 'bhattacharya', 'bose', 'ghosh',
    'das', 'dutta', 'sen', 'ray', 'sarkar', 'chakraborty', 'ganguly',
    'basu', 'mitra', 'saha', 'nandi', 'hazra', 'biswas', 'barua',
    'choudhury', 'majumdar', 'kar',
    # ── South Indian — Tamil ──
    'raman', 'sundaram', 'raghavan', 'subramaniam', 'subramanian',
    'venkatesh', 'natarajan', 'ramachandran', 'srinivasan', 'anantharaman',
    'iyer', 'iyengar', 'krishnamurthy', 'seshadri', 'venkatesan',
    'gopalakrishnan', 'balasubramanian', 'chandrasekaran', 'muthukrishnan',
    'thirumalai', 'palaniswami', 'shanmugam', 'murugan', 'selvam',
    'arumugam', 'ramasamy', 'lakshmi',
    # ── South Indian — Telugu ──
    'reddy', 'naidu', 'rao', 'raju', 'prasad', 'murthy', 'chowdary',
    'varma', 'goud', 'setty', 'chetty', 'achary',
    # ── South Indian — Kannada ──
    'hegde', 'shetty', 'bhat', 'nayak', 'gowda',
    # ── South Indian — Malayalam / Kerala ──
    'nair', 'menon', 'pillai', 'kurup', 'warrier', 'namboothiri',
    'unnikrishnan', 'madhavan', 'gopinath', 'padmanabhan',
    # ── Jain ──
    'jain', 'kothari', 'doshi', 'oswal', 'lodha',
    # ── North Indian — commercial/Khatri ──
    'bajaj', 'kapoor', 'malhotra', 'bhatia', 'chopra', 'khanna',
    'tandon', 'vohra', 'suri', 'kohli', 'luthra', 'mehra',
    # ── Rajasthani ──
    'rathore', 'shekhawat', 'rajput', 'bhargava', 'purohit',
    # ── Other common ──
    'kumar', 'krishnan', 'mahajan', 'thapar', 'dhawan',
    'mani', 'mohan', 'narayan', 'chandra', 'kishore',
    'saini', 'rawat', 'negi', 'bisht', 'pandit',
    'dikshit', 'kashyap', 'tyagi', 'taneja', 'ahirwar',
    'swamy', 'murali', 'raghunath', 'jagannath',
    'ranganathan', 'parthasarathy', 'viswanathan',
    # ── Muslim South Asian ──
    'khan', 'alam', 'hossain', 'hasan', 'islam', 'rahman', 'uddin',
    'siddiqui', 'ansari', 'qureshi', 'shaikh', 'mirza',
    # ── Nepali ──
    'shrestha', 'poudel', 'adhikari', 'karki', 'khanal', 'dahal',
    'ghimire', 'thapa', 'gurung', 'tamang', 'basnet', 'bhandari',
    'sapkota', 'lamichhane', 'rijal', 'subedi', 'bhattarai',
    # ── More common South Asian ──
    'thakkar', 'roy', 'chowdhury', 'dey', 'acharya', 'razdan',
    'khetan', 'nakka', 'nagapurkar', 'vallurupalli', 'perera',
    'mondal', 'barman', 'bhowmick', 'shahinuzzaman',
}

# Indian surnames that overlap with other ethnicities
AMBIGUOUS_INDIAN_SURNAMES = {
    'shah',     # also Iranian/Middle Eastern
    'das',      # also German/Bengali — usually Indian in US PhD context
    'ray',      # also French/English
    'sen',      # also various
    'gill',     # also Scottish/Irish
    'mann',     # also German
    'more',     # also English/Irish
    'modi',     # distinctive but small sample
    'nayak',    # could be other South Asian
}

# Common Indian given names (for validating ambiguous Indian surnames)
INDIAN_GIVEN_NAMES = {
    # Male
    'rahul', 'amit', 'anil', 'ajay', 'vijay', 'rajesh', 'suresh', 'ramesh',
    'sanjay', 'manoj', 'vinod', 'ashok', 'arun', 'arvind', 'deepak', 'dinesh',
    'ganesh', 'girish', 'gopal', 'hari', 'hemant', 'jagdish', 'kamal',
    'kiran', 'krishna', 'mahesh', 'mukesh', 'naresh', 'pankaj', 'pramod',
    'prakash', 'prashant', 'praveen', 'rajiv', 'rajan', 'rakesh', 'ravi',
    'rohit', 'sachin', 'sandeep', 'satish', 'shashi', 'shyam', 'sunil',
    'sushil', 'umesh', 'varun', 'vikas', 'vinay', 'vivek', 'yogesh',
    'aarav', 'arjun', 'dhruv', 'gautam', 'harsh', 'ishaan', 'jai',
    'kartik', 'manish', 'nikhil', 'pranav', 'rohan', 'sagar', 'tanmay',
    'abhinav', 'akash', 'anand', 'anirudh', 'ashish', 'chirag', 'gaurav',
    'hitesh', 'jatin', 'kunal', 'mohit', 'neeraj', 'piyush', 'pradeep',
    'rajat', 'sameer', 'saurabh', 'tarun', 'tushar', 'utkarsh', 'vishal',
    'siddharth', 'shreyas', 'soham', 'tejas', 'vignesh', 'aditya',
    'bharat', 'chetan', 'devendra', 'govind', 'harish', 'jayant',
    'karthik', 'laxman', 'mohan', 'narendra', 'om', 'param', 'rajeev',
    'shivam', 'subhash', 'trilok', 'uday', 'venkat', 'yash',
    # Female
    'priya', 'anita', 'sunita', 'kavita', 'neha', 'pooja', 'swati',
    'anjali', 'deepa', 'divya', 'jyoti', 'lakshmi', 'meena', 'nandini',
    'padma', 'radha', 'rekha', 'sarita', 'seema', 'shobha', 'sita',
    'smita', 'sneha', 'usha', 'vani', 'vidya', 'archana', 'bhavna',
    'chitra', 'geeta', 'hema', 'indira', 'jayashree', 'kamala',
    'lalita', 'madhuri', 'nisha', 'pallavi', 'rashmi', 'sangeeta',
    'shilpa', 'sujata', 'tanvi', 'uma', 'vandana', 'yamini',
    'aditi', 'amrita', 'aparna', 'aishwarya', 'bhavani', 'devi',
    'durga', 'gauri', 'gita', 'isha', 'jaya', 'kriti', 'lata',
    'mallika', 'meghna', 'nivedita', 'parvati', 'preeti', 'revathi',
    'rukmini', 'savitri', 'shanti', 'shruti', 'sonal', 'tara',
    'varsha', 'veena',
}
IRANIAN_SURNAMES = {
    # Common Iranian/Persian surnames
    'mohammadi', 'hosseini', 'hashemi', 'mousavi', 'rezaei', 'ahmadi',
    'karimi', 'moradi', 'abbasi', 'ghorbani', 'rahimi', 'sadeghi',
    'jafari', 'taheri', 'nazari', 'bagheri', 'asadi', 'kazemi',
    'rostami', 'soleimani', 'ebrahimi', 'alizadeh', 'shirazi',
    'esfahani', 'tehrani', 'tabatabaei', 'rahmani', 'ansari',
    'dehghani', 'esmaeili', 'farahani', 'ghaffari', 'habibi',
    'hassani', 'jalali', 'kamali', 'lotfi', 'madani', 'nouri',
    'omidi', 'rashidi', 'saberi', 'tavakoli', 'yousefi', 'zarei',
    'amiri', 'bakhtiari', 'darvishi', 'eslami', 'fattahi',
    'golestani', 'heidari', 'jamshidi', 'khosravi', 'mahdavi',
    'najafi', 'norouzi', 'pakdel', 'rafiee', 'sajjadi',
    'toghiani', 'vatankhah', 'yazdani', 'zamani', 'zolfaghari',
    'akbari', 'bashiri', 'daneshmand', 'faraji', 'ghasemi',
    'hakimi', 'irani', 'javadi', 'keshavarz', 'latifi',
    'mohtashami', 'nikkhah', 'panahi', 'ranjbar', 'samadi',
    'tabrizi', 'vahidi', 'zandi', 'afshar', 'bayat',
    'dadkhah', 'emami', 'ferdowsi', 'gilani', 'homayoun',
    'izadi', 'kabiri', 'maleki', 'nafisi', 'parsa',
    'rouhani', 'shahbazi', 'talebi', 'vafaei', 'yekta',
    'attar', 'bahrami', 'daneshi', 'erfani', 'firouzi',
    'gorji', 'hamidi', 'kamran', 'mazaheri', 'noori',
    'pirhadi', 'salari', 'taghavi', 'vakili', 'zargar',
    'akhlaghi', 'derakhshan', 'etemadi', 'ghazanfari',
    'hafezi', 'khorasani', 'mirzaei', 'parvizi', 'safavi',
    'tolouei', 'zargham', 'asghari', 'fotouhi', 'khatibi',
    'moghaddam', 'niknejad', 'pourghaz', 'saremi', 'shahidi',
    'mostofi', 'naderi', 'ramezani', 'shariati', 'sadeghizadeh',
    # Batch 2 — additional common Iranian surnames
    'sadati', 'valipour', 'alikhani', 'beheshti', 'dastjerdi',
    'farrokhi', 'ghavami', 'hajizadeh', 'kalantari', 'motamedi',
    'nikpour', 'rezazadeh', 'sharifian', 'taghizadeh', 'zargari',
    'abedi', 'amini', 'dastani', 'faghihi', 'golzar',
    'heydari', 'karami', 'mansouri', 'naseri', 'rahimian',
    'safaei', 'shahram', 'tabatabai', 'vakilian', 'zafari',
    'talaei', 'mohammadian', 'akhavan', 'barghi', 'darabi',
    'aghaee', 'monjezi', 'pourhassan', 'bazargan', 'fakhr',
}

# Iranian surname suffixes (very distinctive patterns)
IRANIAN_SUFFIXES = (
    'zadeh', 'zade', 'pour', 'pur', 'nejad', 'nezhad',
    'khah', 'mand', 'doust', 'dust', 'yar', 'far',
)

TURKISH_SURNAMES = {
    # Common Turkish surnames
    'yilmaz', 'kaya', 'demir', 'celik', 'sahin', 'dogan', 'kilic',
    'arslan', 'aydin', 'ozturk', 'yildiz', 'erdogan', 'polat',
    'ozdemir', 'aksoy', 'yildirim', 'koc', 'ozkan', 'kaplan',
    'tekin', 'acar', 'bulut', 'cinar', 'erdem', 'gul',
    'gunes', 'ilhan', 'karaca', 'kurt', 'ozcan', 'sezer',
    'simsek', 'toprak', 'unal', 'uzun', 'yavuz', 'aktas',
    'aslan', 'bozkurt', 'caliskan', 'cetin', 'duran',
    'gokce', 'guler', 'inan', 'korkmaz', 'ozer', 'saglam',
    'sonmez', 'tas', 'turan', 'uslu', 'vural', 'yaman',
    'bayrak', 'duman', 'eker', 'firat', 'gonul', 'inal',
    'kartal', 'oguz', 'pektas', 'sari', 'tunc', 'yasar',
    'zengin', 'altun', 'basar', 'coban', 'dursun', 'ekinci',
    'guzel', 'hacioglu', 'ince', 'kara', 'mert', 'oner',
    'pinar', 'soylu', 'tatli', 'ucar', 'vardar', 'yalcin',
    'ayhan', 'bicer', 'cakir', 'deniz', 'elmas', 'guney',
    'isik', 'kilinc', 'mutlu', 'okur', 'savas', 'toker',
    'uysal', 'yigit', 'akbas', 'baran', 'ciftci', 'eken',
    'gecit', 'keskin', 'orhan', 'senturk', 'turhan', 'yoruk',
    'aggul', 'erkmen', 'gezek', 'turkel', 'buyukdagtas',
    'alkan', 'basaran', 'cigdem', 'ercan', 'gullu',
    'kahraman', 'ozgur', 'sevim', 'tanir', 'ustun',
    'gungor', 'bilgin', 'kocak', 'tarim', 'bayram',
    # Batch 2 — additional Turkish surnames
    'algan', 'guzey', 'akgun', 'akin', 'alpay',
    'altay', 'arikan', 'atan', 'avci', 'balci', 'balta',
    'can', 'colak', 'demirel', 'dincer', 'ergin', 'erol',
    'gokcen', 'gunduz', 'kalkan', 'koc', 'kose', 'ozbek',
    'ozturk', 'sahin', 'sener', 'taner', 'tekeli', 'tugcu',
    'unlu', 'yildiz', 'yuksel',
}

# Turkish surname suffixes
TURKISH_SUFFIXES = ('oglu', 'oğlu')

ARABIC_SURNAMES = {
    # Common Arabic surnames (without Al- prefix, which is handled separately)
    'ahmed', 'ahmad', 'ali', 'hassan', 'hussein', 'hussain',
    'ibrahim', 'khalil', 'mohammed', 'muhammad', 'omar', 'omer',
    'said', 'saleh', 'youssef', 'yousef', 'nasser', 'mansour',
    'haddad', 'khoury', 'farah', 'jabbar', 'hamdan', 'qasim',
    'rashid', 'sultan', 'wahab', 'zaki', 'abdallah', 'abdelrahman',
    'abdelaziz', 'bakr', 'darwish', 'faisal', 'ghazal', 'habib',
    'ismail', 'jamil', 'karim', 'latif', 'majid', 'mustafa',
    'nabil', 'othman', 'qadir', 'rashed', 'salam', 'tariq',
    'wasim', 'yaqub', 'zahir', 'abadi', 'badawi', 'dagher',
    'eid', 'farhat', 'ghanem', 'hamad', 'issa', 'jubran',
    'kassar', 'masri', 'nassar', 'obeid', 'sabbagh', 'taha',
    'awad', 'bishara', 'chahine', 'diab', 'elias', 'fares',
    'hanna', 'jaber', 'kallas', 'makhoul', 'nasr', 'rami',
    'saliba', 'touma', 'wehbe', 'yacoub', 'zein', 'amin',
    'abubakar', 'asaad', 'barakat', 'daoud', 'estfan',
    'ghandour', 'hamza', 'karam', 'maroun', 'najjar',
    'rizk', 'samaha', 'turk', 'zeidan', 'ayoub', 'badr',
    'chehab', 'fakhouri', 'geha', 'harb', 'jundi',
    'khalife', 'moussa', 'nouh', 'sleiman', 'tannous',
    'yassin', 'ayyad', 'halabi', 'moustafa', 'rahal',
    'shaaban', 'assaad', 'bazzi', 'ghani', 'sharif',
    # Batch 2 — additional Arabic surnames
    'jawad', 'magzoub', 'khaled', 'farid', 'abedin',
    'baamran', 'almusafir', 'naddaf', 'obaidi',
    # Batch 3 — from screenshot review
    'fayek', 'gomaa', 'hemida', 'riad', 'sabri', 'tafeeq',
    'zouli', 'efhaima', 'shariff', 'taha',
    'abdallah',
}

# Arabic surname prefixes (very distinctive)
ARABIC_PREFIXES = ('al-', 'al ', 'el-', 'el ', 'abu ', 'abd ', 'abdul', 'abdel')

# For non-hyphenated joined "Al" names, exclude common English surnames
_ENGLISH_AL_NAMES = {
    'albert', 'albers', 'alberti', 'albertini', 'albertson', 'albrecht',
    'albright', 'albath', 'albin', 'alcorn', 'alcott',
    'aldag', 'alden', 'alder', 'alderman', 'alderson', 'aldrich', 'aldridge',
    'alexander', 'alfaro', 'alferink', 'alford', 'alfred', 'algood', 'alger',
    'allan', 'allard', 'allen', 'allender', 'alley', 'allison', 'allman', 'allred',
    'almond', 'alonso', 'alper', 'alpert', 'alston', 'altieri', 'altman', 'alton',
    'alvarado', 'alvarez', 'alvord', 'alvis', 'alvey',
}
# Consonants that follow 'al' in Arabic names (not vowels or 'l')
_ARABIC_AL_CONSONANTS = set('bcdfghjkmnqrstvwxyz')

# fmt: on


def get_surname(name_str: str) -> str:
    """Extract surname from 'Last, First' or 'First Last' format.
    For hyphenated surnames like 'Ebrahimi-Asl', returns the base part 'ebrahimi'."""
    name_str = name_str.strip()
    if not name_str:
        return ''
    if ',' in name_str:
        raw = name_str.split(',')[0].strip().lower()
    else:
        parts = name_str.split()
        raw = parts[-1].strip().lower() if parts else ''
    # For hyphenated surnames, return first part (the family name root)
    if '-' in raw:
        return raw.split('-')[0]
    return raw


def get_given_name(name_str: str) -> str:
    """Extract given name from 'Last, First' format."""
    if ',' not in name_str:
        return ''
    return name_str.split(',', 1)[1].strip().lower()


def has_chinese_given_name(name_str: str) -> bool:
    """Check if given name looks like Chinese pinyin."""
    given = get_given_name(name_str)
    if not given:
        return False
    parts = given.replace('-', ' ').split()
    if not parts:
        return False
    return parts[0] in PINYIN_SYLLABLES or (
        len(parts) >= 2 and all(p in PINYIN_SYLLABLES for p in parts[:2])
    )


def classify(name_str: str) -> tuple:
    """
    Classify a name by likely origin.

    Returns:
        (category, confidence) where category is one of:
        'chinese', 'korean', 'vietnamese', 'indian', 'iranian', 'turkish',
        'arabic', 'excluded_ambiguous', 'other'
        and confidence is 'high', 'medium', or 'n/a'
    """
    surname = get_surname(name_str)
    if not surname:
        return ('other', 'n/a')

    if surname in EXCLUDE_SURNAMES:
        return ('excluded_ambiguous', 'n/a')

    if surname in CHINESE_SURNAMES:
        if surname in AMBIGUOUS_SURNAMES:
            conf = 'high' if has_chinese_given_name(name_str) else 'medium'
        else:
            conf = 'high'
        return ('chinese', conf)

    korean_only = KOREAN_SURNAMES - CHINESE_SURNAMES
    if surname in korean_only:
        return ('korean', 'high')

    if surname in VIETNAMESE_SURNAMES:
        return ('vietnamese', 'high')

    if surname in INDIAN_SURNAMES:
        if surname in AMBIGUOUS_INDIAN_SURNAMES:
            conf = 'high' if has_indian_given_name(name_str) else 'medium'
        else:
            conf = 'high'
        return ('indian', conf)

    # Iranian — check suffixes first (very distinctive), then surname list
    if any(surname.endswith(sfx) for sfx in IRANIAN_SUFFIXES):
        return ('iranian', 'high')
    if surname in IRANIAN_SURNAMES:
        return ('iranian', 'high')

    # Turkish — check suffixes, then surname list
    if any(surname.endswith(sfx) for sfx in TURKISH_SUFFIXES):
        return ('turkish', 'high')
    if surname in TURKISH_SURNAMES:
        return ('turkish', 'high')

    # Iranian — also check 'pour' prefix (Pourhassan, Pourmohammad)
    if surname.startswith('pour') and len(surname) > 5:
        return ('iranian', 'high')

    # Arabic — check prefixes (Al-, Abu, Abd), then surname list
    full_surname = name_str.split(',')[0].strip().lower() if ',' in name_str else ''
    if any(full_surname.startswith(pfx) for pfx in ARABIC_PREFIXES):
        return ('arabic', 'high')
    # Non-hyphenated joined Al- prefix: "Alghazali", "Alabdulhady", etc.
    # Exclude common English surnames like Albert, Aldrich, etc.
    if (full_surname.startswith('al') and len(full_surname) > 4
            and full_surname not in _ENGLISH_AL_NAMES
            and (full_surname[2:3] in _ARABIC_AL_CONSONANTS
                 or full_surname[2:].startswith(('abd', 'abu')))):
        return ('arabic', 'high')
    # Surnames containing 'allah' or 'ullah' (Deef-Allah, Saifullah, etc.)
    if 'allah' in full_surname or 'ullah' in full_surname:
        return ('arabic', 'high')
    if surname in ARABIC_SURNAMES:
        return ('arabic', 'medium')

    return ('other', 'n/a')


def is_chinese(name_str: str) -> bool:
    """Simple boolean: is this name likely Chinese?"""
    cat, _ = classify(name_str)
    return cat == 'chinese'


def is_chinese_high_confidence(name_str: str) -> bool:
    """Is this name likely Chinese with high confidence?"""
    cat, conf = classify(name_str)
    return cat == 'chinese' and conf == 'high'


def is_indian(name_str: str) -> bool:
    """Simple boolean: is this name likely Indian?"""
    cat, _ = classify(name_str)
    return cat == 'indian'


def is_indian_high_confidence(name_str: str) -> bool:
    """Is this name likely Indian with high confidence?"""
    cat, conf = classify(name_str)
    return cat == 'indian' and conf == 'high'


def has_indian_given_name(name_str: str) -> bool:
    """Check if given name looks Indian."""
    given = get_given_name(name_str)
    if not given:
        return False
    parts = given.replace('-', ' ').split()
    if not parts:
        return False
    return parts[0].lower() in INDIAN_GIVEN_NAMES
