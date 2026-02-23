from . import config

class RiskManager:
    def __init__(self, initial_capital=None):
        self.capital = initial_capital or config.INITIAL_CAPITAL
        self.risk_per_trade_percent = config.RISK_PER_TRADE_PERCENT
        self.max_risk_amount = config.MAX_RISK_PER_TRADE
        self.current_capital = self.capital

    def update_capital(self, current_capital):
        self.current_capital = current_capital

    def calculate_position_size(self, entry_price, sl_price):
        """
        Calculates position size based on risk parameters.
        """
        if entry_price <= 0 or sl_price <= 0:
            return 0

        risk_per_unit = abs(entry_price - sl_price)

        if risk_per_unit == 0:
            return 0 # Avoid division by zero

        # Risk Amount Calculation
        # Risk 2% of Initial Capital or Current Capital?
        # Usually Initial Capital for fixed fractional, or Current for compounding.
        # User requirement: "Risk per trade: 2% max (10,000 per trade)"
        # "Initial Capital: 5,00,000" -> 2% is 10,000.
        # So we can just use min(Current * 0.02, 10000) or just min(Initial * 0.02, 10000).
        # "Risk per trade: 2% max" usually implies 2% of current account balance, but capped at some value?
        # Or 2% of Initial (Fixed Risk).
        # Given "Risk per trade: 2% max (10,000 per trade)", and Initial 5L.
        # 2% of 5L is 10k.
        # I will use 2% of Current Capital, capped at 10k.

        risk_amount = self.current_capital * self.risk_per_trade_percent
        risk_amount = min(risk_amount, self.max_risk_amount)

        qty = int(risk_amount / risk_per_unit)

        return qty

    def check_drawdown(self):
        # Implement if needed
        pass
