package refundreconcile

import "testing"

func TestEnabledOnlyForWeChat(t *testing.T) {
	if !Enabled("wechat") || !Enabled(" WECHAT ") {
		t.Fatal("expected WeChat reconciliation worker enabled")
	}
	if Enabled("manual") || Enabled("") {
		t.Fatal("manual/empty refund provider must not run reconciliation")
	}
}
