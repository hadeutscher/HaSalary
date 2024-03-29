import math

### Universal constants ###
AVERAGE_SALARY = 10551

### Income Tax law ###
INCOME_TAX_POINT_WORTH = 2616 / 12  # Section 33a

# Section 121
INCOME_TAX_STEPS = [
    (75480 / 12, 0.10),
    (108360 / 12, 0.14),
    (173880 / 12, 0.20),
    (241680 / 12, 0.31),
    (502920 / 12, 0.35),
    (647640 / 12, 0.47),
    (math.inf, 0.50)
]

PENSION_REIMBURSE = 0.35  # Section 45a(b)
# Section 47(a)(1), also see 45a(d)(2)(b)(2), 45a(e)(2)(b)(2)(a)
PENSION_REIMBURSE_PAYMENTS_MAX = 104400 * 0.07 / 12
PENSION_EMPLOYER_TAX_EXEMPT_PAYMENTS_MAX = (
    AVERAGE_SALARY * 2.5) * 0.075  # Section 3(e3)(2)
PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX = 34900 / 12  # Section 3(e3)(2)
REPARATIONS_PULL_TAX_EXEMPT_MAX = 12340 / 12  # Section 9(7a)(a)(2)

PENSION_INDEPENDENT_MAX_SALARY = (104400 * 2) / 12 # Section 47(a)(1)(1), see also 45a(e)(2)(b)(1)
PENSION_INDEPENDENT_RATE_WRITEOFF = 0.11 # Section 47(b1)(1)
PENSION_INDEPENDENT_RATE_REIMBURSE = 0.05 # Section 45a(e)(2)(b)(1)
PENSION_INDEPENDENT_RATE_REIMBURSE_ACA = 0.005 # Section 45a(f)

STUDY_FUND_EMPLOYEE = 0.025 # Section 16a(c){הפקדה מוטבת}(2)(b)
STUDY_FUND_EMPLOYER = STUDY_FUND_EMPLOYEE * 3 # Section 16a(c){הפקדה מוטבת}(2)(c)
STUDY_FUND_TAX_EXEMPT_MAX = 15712  # Section 3(e)
# Section 17(5a)
STUDY_FUND_INDEPENDENT = 0.045
STUDY_FUND_INDEPENDENT_MAX_SALARY = 263000 / 12


### National Insurance law ###
BASE_NUMBER_3 = 8804
NATIONAL_INSURANCE_STEPS = [
    (AVERAGE_SALARY * 0.6, 0.004),
    (BASE_NUMBER_3 * 5, 0.07)
]

HEALTH_INSURANCE_STEPS = [
    (AVERAGE_SALARY * 0.6, 0.031),
    (BASE_NUMBER_3 * 5, 0.05)
]

EMPLOYER_NATIONAL_INSURANCE_STEPS = [
    (AVERAGE_SALARY * 0.6, 0.0355),
    (BASE_NUMBER_3 * 5, 0.076)
]

INDEPENDENT_NATIONAL_INSURANCE_STEPS = [
    (AVERAGE_SALARY * 0.6, 0.0287),
    (BASE_NUMBER_3 * 5, 0.1283)
]
