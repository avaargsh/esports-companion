package workerobs

import "time"

type CycleObserver interface {
	ObserveCycle(
		worker string,
		duration time.Duration,
		processed int,
		failures int,
		err error,
	)
}

type NopObserver struct{}

func (NopObserver) ObserveCycle(
	_ string,
	_ time.Duration,
	_ int,
	_ int,
	_ error,
) {
}

func OrNop(observer CycleObserver) CycleObserver {
	if observer == nil {
		return NopObserver{}
	}
	return observer
}
